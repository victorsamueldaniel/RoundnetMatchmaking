import { useEffect, useMemo, useState } from 'react'
import { viewSession } from '../api'
import { toast } from '../components/toast'
import { Button, Card, Modal, Segmented } from '../components/ui'
import { deltaColor, signed, SPEC_ABBREV } from '../lib/format'
import { useStore, type PendingSwap } from '../store'
import type { RoundDoc, SessionDocument, SessionView, SlotView } from '../types'

type Slot = { round: number; name: string }

/** Swap two players inside one round of a session document (teams or bench). */
export function applySwaps(document: SessionDocument, swaps: PendingSwap[]): SessionDocument {
  if (!swaps.length) return document
  const rounds: RoundDoc[] = document.rounds.map((r) => ({
    ...r,
    games: r.games.map((g) => ({ team_a: [...g.team_a], team_b: [...g.team_b] })),
    bench: [...r.bench],
  }))
  for (const swap of swaps) {
    const round = rounds[swap.round]
    const lists = [...round.games.flatMap((g) => [g.team_a, g.team_b]), round.bench]
    const locate = (name: string) => {
      for (const list of lists) {
        const index = list.indexOf(name)
        if (index >= 0) return { list, index }
      }
      return null
    }
    const a = locate(swap.a)
    const b = locate(swap.b)
    if (a && b) {
      a.list[a.index] = swap.b
      b.list[b.index] = swap.a
    }
  }
  return { ...document, rounds }
}

const TERM_LABELS: Record<string, string> = {
  high_level_teammates: 'High-level teammate',
  high_level_opponents: 'High-level opponents',
  never_met: 'Never met',
  same_teammate: 'Same teammate',
  same_people: 'Same people',
  gender_preference: 'Gender preference not satisfied',
  minority: 'Minority gender',
  level_bonus: 'Level bonus',
}

function slotIn(view: SessionView | null, round: number, name: string): SlotView | undefined {
  const r = view?.rounds[round]
  if (!r) return undefined
  for (const g of r.games) {
    const slot = [...g.team_a, ...g.team_b].find((p) => p.name === name)
    if (slot) return slot
  }
  return undefined
}

function Details({ slot, round, pending }: { slot: SlotView | undefined; round: number; pending: boolean }) {
  if (!slot) return <p className="text-sm text-muted">Sitting out this round.</p>
  const b = slot.breakdown
  return (
    <div className="font-mono text-xs leading-relaxed">
      <p className="mb-1 text-sm font-semibold text-brand-yellow">
        {slot.name} · Round {round + 1}
        {pending && <span className="ml-2 text-xs font-normal text-muted">[pending]</span>}
      </p>
      {b?.spectrum && (
        <>
          <div className="grid grid-cols-3 gap-x-3">
            {Object.entries(b.spectrum.values).map(([spec, value]) => (
              <span key={spec} className={b.spectrum!.triggered[spec as keyof typeof b.spectrum.values] ? 'text-white' : 'text-muted'}>
                {SPEC_ABBREV[spec]}:{value}
                {b.spectrum!.triggered[spec as keyof typeof b.spectrum.values] ? ' ✓' : ''}
              </span>
            ))}
          </div>
          <p>
            → Chosen: {b.spectrum.chosen ? SPEC_ABBREV[b.spectrum.chosen] : 'none'} {signed(b.terms.spectrum ?? 0, 0)}
          </p>
        </>
      )}
      {b &&
        Object.entries(b.terms)
          .filter(([key, value]) => key !== 'spectrum' && value !== 0)
          .map(([key, value]) => (
            <p key={key} className="flex justify-between gap-4">
              <span>
                {TERM_LABELS[key] ?? key}
                {key === 'never_met' ? ` (${b.new_people} new)` : ''}
              </span>
              <span className={value > 0 ? 'text-gain' : 'text-loss'}>{signed(value, 1)}</span>
            </p>
          ))}
      {!!slot.pair_bonus && (
        <p className="flex justify-between gap-4">
          <span>Preferred pair</span>
          <span className="text-gain">{signed(slot.pair_bonus, 1)}</span>
        </p>
      )}
      <p className="mt-1 flex justify-between gap-4 border-t border-line pt-1 font-semibold">
        <span>Total</span>
        <span>{signed((slot.gain ?? 0) + (slot.pair_bonus ?? 0), 1)}</span>
      </p>
    </div>
  )
}

export function EditorScreen() {
  const document = useStore((s) => s.document)!
  const view = useStore((s) => s.view)
  const swaps = useStore((s) => s.pendingSwaps)
  const setSwaps = useStore((s) => s.setPendingSwaps)
  const history = useStore((s) => s.history)
  const commit = useStore((s) => s.commitSession)
  const restore = useStore((s) => s.restoreVersion)
  const [selection, setSelection] = useState<Slot[]>([])
  const [latestPreview, setPreview] = useState<SessionView | null>(null)
  const [focus, setFocus] = useState<Slot | null>(null)
  const [detailsMode, setDetailsMode] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [mobileRound, setMobileRound] = useState(0)
  const [busy, setBusy] = useState(false)

  const working = useMemo(() => applySwaps(document, swaps), [document, swaps])

  useEffect(() => {
    if (!swaps.length) return
    let cancelled = false
    const timer = setTimeout(() => {
      viewSession(working).then(
        (v) => !cancelled && setPreview(v),
        (e: Error) => !cancelled && toast('error', e.message),
      )
    }, 120)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [working, swaps.length])

  const preview = swaps.length ? latestPreview : null
  const levels = useMemo(() => new Map(document.players.map((p) => [p.id, Number(p.Level)])), [document])
  const pairKeys = useMemo(() => new Set(document.preferred_pairs.map((p) => [...p.players].sort().join('|'))), [document])
  const pendingRounds = new Set(swaps.map((s) => s.round))

  const overBenched = useMemo(() => {
    const played = new Map(working.players.map((p) => [p.id, 0]))
    for (const r of working.rounds) for (const g of r.games) for (const n of [...g.team_a, ...g.team_b]) played.set(n, (played.get(n) ?? 0) + 1)
    const max = Math.max(...played.values())
    return new Set([...played].filter(([, n]) => max - n >= 2).map(([name]) => name))
  }, [working])

  if (!view) return <p className="py-16 text-center text-muted">Loading session…</p>

  const pick = (slot: Slot) => {
    if (detailsMode) {
      setFocus(slot)
      setDetailsOpen(true)
      return
    }
    const already = selection.find((s) => s.name === slot.name && s.round === slot.round)
    if (already) {
      setSelection(selection.filter((s) => s !== already))
      return
    }
    const next = [...selection.filter((s) => s.name !== slot.name), slot]
    if (next.length < 2) {
      setSelection(next)
      return
    }
    const [a, b] = next
    setSelection([])
    if (a.round !== b.round) {
      toast('error', 'Can only swap players within the same round!')
      return
    }
    setSwaps([...swaps, { round: a.round, a: a.name, b: b.name }])
  }

  const apply = async () => {
    if (!swaps.length) {
      toast('info', 'No pending changes to apply.')
      return
    }
    setBusy(true)
    try {
      const next = await viewSession(working)
      commit(working, next, next.summary.score)
      setPreview(null)
      toast(
        'success',
        `Applied ${swaps.length} change(s) successfully!\nNew mean happiness: ${next.summary.mean.toFixed(2)}\nNew std happiness: ${next.summary.std.toFixed(2)}`,
      )
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const restoreAt = async (index: number) => {
    try {
      const v = await viewSession(history[index].document)
      restore(index, v)
      setSelection([])
      toast('info', index === 0 ? 'Initial session restored.' : `Version after apply ${index} restored.`)
    } catch (e) {
      toast('error', `Could not restore session:\n${(e as Error).message}`)
    }
  }

  const lambda = Number(document.params.lambda_weight ?? 2)
  const percentile = Number(document.params.percentile ?? 33)
  const focusedSlot = focus ? slotIn(pendingRounds.has(focus.round) ? preview : view, focus.round, focus.name) : undefined

  const renderPlayer = (name: string, round: number, benched: boolean) => {
    const pending = pendingRounds.has(round)
    const base = slotIn(view, round, name)
    const now = pending ? slotIn(preview, round, name) : base
    const selected = selection.some((s) => s.name === name && s.round === round)
    const sad = benched && overBenched.has(name)
    let background: string | null = null
    let middle = ''
    if (!benched) {
      const spec = view.rounds[round] && document.params.spectrum !== false ? now?.spec : null
      middle = spec ? SPEC_ABBREV[spec] : ''
      if (pending && preview) {
        const delta = (now?.gain ?? 0) + (now?.pair_bonus ?? 0) - ((base?.gain ?? 0) + (base?.pair_bonus ?? 0))
        background = deltaColor(delta)
        if (background) middle = `${middle} [${signed(delta)}]`.trim()
      }
    } else if (sad) {
      middle = 'SAD!'
    }
    return (
      <button
        key={name}
        onClick={() => pick({ round, name })}
        onMouseEnter={() => setFocus({ round, name })}
        className={`flex min-h-16 min-w-0 flex-1 flex-col items-center justify-center rounded-md border px-1 py-1 text-center text-xs leading-tight transition-colors ${
          selected
            ? 'border-brand-yellow bg-brand-yellow text-black ring-2 ring-brand-yellow'
            : sad
              ? 'border-black bg-black text-white'
              : 'border-black/10 bg-white text-black'
        }`}
        style={!selected && !sad && background ? { background } : undefined}
      >
        <span className="w-full truncate font-semibold">{name}</span>
        <span className="h-4 text-[11px] opacity-80">{middle}</span>
        <span className="opacity-70">Lvl {levels.get(name)}</span>
      </button>
    )
  }

  const renderRound = (round: RoundDoc, r: number) => (
    <section key={r} className="min-w-0 overflow-hidden rounded-xl border border-line bg-panel">
      <h3 className="bg-brand-red px-3 py-2 text-center font-bold tracking-wide">ROUND {r + 1}</h3>
      <div className="space-y-2 p-2">
        {round.games.map((game, g) => {
          const mean = (team: string[]) => team.reduce((sum, n) => sum + (levels.get(n) ?? 0), 0) / team.length
          const diff = mean(game.team_a) - mean(game.team_b)
          const gold = (team: string[]) => pairKeys.has([...team].sort().join('|'))
          return (
            <div key={g} className="rounded-lg bg-raised p-2">
              <p className="mb-1.5 text-center text-[11px] text-muted italic">
                {round.type_preference} | {round.gender_preference}
              </p>
              <div className={`flex gap-1 rounded-md p-1 ${gold(game.team_a) ? 'bg-[#FFD700]' : 'bg-[#D0E8FF]'}`}>
                {game.team_a.map((n) => renderPlayer(n, r, false))}
              </div>
              <p className="py-0.5 text-center text-xs font-semibold">
                <span className={diff >= 0 ? 'text-[#7fa6ea]' : 'text-loss'}>{Math.abs(diff) < 0.05 ? '0.0' : signed(diff)}</span>
                <span className="ml-2 text-brand-yellow">VS</span>
              </p>
              <div className={`flex gap-1 rounded-md p-1 ${gold(game.team_b) ? 'bg-[#FFD700]' : 'bg-[#FFE0E0]'}`}>
                {game.team_b.map((n) => renderPlayer(n, r, false))}
              </div>
            </div>
          )
        })}
        {round.bench.length > 0 && (
          <div className="rounded-lg bg-[#FFF8DC] p-2">
            <p className="mb-1 text-xs font-semibold text-black">Not playing</p>
            <div className="grid grid-cols-2 gap-1">{round.bench.map((n) => renderPlayer(n, r, true))}</div>
          </div>
        )}
      </div>
    </section>
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-brand-yellow">Interactive games editor</h2>
          <p className="text-sm text-soft">
            {detailsMode ? 'Tap a player to see how their happiness is computed.' : 'Tap two players of the same round to swap them.'}
          </p>
        </div>
        <Segmented
          label="Tap mode"
          value={detailsMode ? 'details' : 'swap'}
          options={[
            { value: 'swap', label: 'Swap' },
            { value: 'details', label: 'Details' },
          ]}
          onChange={(v) => setDetailsMode(v === 'details')}
        />
      </div>

      {swaps.length > 0 && (
        <div className="sticky bottom-16 z-20 flex items-center gap-2 rounded-xl border border-brand-yellow/40 bg-panel/95 px-3 py-2 shadow-lg backdrop-blur lg:hidden">
          <span className="flex-1 text-sm">
            {swaps.length} change(s) pending
          </span>
          <Button className="min-h-9" onClick={() => setSwaps(swaps.slice(0, -1))}>
            Undo
          </Button>
          <Button variant="primary" className="min-h-9" disabled={busy} onClick={apply}>
            Apply
          </Button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0 space-y-3">
          <div className="lg:hidden">
            <Segmented
              label="Round"
              value={String(mobileRound)}
              options={working.rounds.map((_, i) => ({ value: String(i), label: `R${i + 1}${pendingRounds.has(i) ? '•' : ''}` }))}
              onChange={(v) => setMobileRound(Number(v))}
            />
          </div>
          <div className="lg:hidden">{working.rounds[mobileRound] && renderRound(working.rounds[mobileRound], mobileRound)}</div>
          <div className="scroll-thin hidden gap-3 overflow-x-auto pb-2 lg:grid" style={{ gridTemplateColumns: `repeat(${working.rounds.length}, minmax(12.5rem, 1fr))` }}>
            {working.rounds.map(renderRound)}
          </div>
        </div>

        <aside className="space-y-4">
          <Card title="Pending changes">
            {swaps.length ? (
              <ol className="space-y-1 text-sm">
                {swaps.map((s, i) => (
                  <li key={i}>
                    {i + 1}. Round {s.round + 1}: {s.a} ↔ {s.b}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-sm text-muted">No changes yet</p>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button disabled={!swaps.length} onClick={() => setSwaps(swaps.slice(0, -1))}>
                Undo last swap
              </Button>
              <Button variant="primary" disabled={busy || !swaps.length} onClick={apply}>
                ⚡ Apply & recalculate
              </Button>
            </div>
          </Card>
          <Card title="Player details">
            {focus ? <Details slot={focusedSlot} round={focus.round} pending={pendingRounds.has(focus.round)} /> : <p className="text-sm text-muted">Hover a player, or use the Details mode on a phone.</p>}
          </Card>
          <Card title={`Score history · mean + ${lambda.toFixed(1)}·bottom ${percentile}%`}>
            <div className="flex flex-wrap gap-2">
              {history.map((entry, i) => {
                const delta = i ? entry.score - history[i - 1].score : 0
                const current = i === history.length - 1
                const tone = !i ? 'bg-[#BBBBBB] text-black' : delta > 0.009 ? 'bg-[#4CAF50]' : delta < -0.009 ? 'bg-[#E53935]' : 'bg-[#BBBBBB] text-black'
                return (
                  <button
                    key={i}
                    disabled={current}
                    onClick={() => restoreAt(i)}
                    title={current ? 'Current version' : 'Restore this version'}
                    className={`rounded-lg px-2.5 py-1.5 text-left text-xs ${tone} ${current ? 'ring-2 ring-brand-yellow' : 'opacity-85 hover:opacity-100'}`}
                  >
                    <span className="block font-semibold">
                      {current ? '► ' : ''}
                      {i ? `Apply ${i}` : 'Initial'}
                    </span>
                    <span className="block font-mono text-sm tabular-nums">{entry.score.toFixed(3)}</span>
                    {i > 0 && <span className="block">{delta > 0.009 ? `▲ +${delta.toFixed(2)}` : delta < -0.009 ? `▼ ${delta.toFixed(2)}` : '≈ 0'}</span>}
                  </button>
                )
              })}
            </div>
          </Card>
        </aside>
      </div>
      <Modal open={detailsOpen && focus !== null} title="Player details" onClose={() => setDetailsOpen(false)}>
        {focus && <Details slot={focusedSlot} round={focus.round} pending={pendingRounds.has(focus.round)} />}
      </Modal>
    </div>
  )
}
