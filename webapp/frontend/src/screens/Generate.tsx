import { type Dispatch, type SetStateAction, useEffect, useMemo, useRef, useState } from 'react'
import { exportPlayers, generateSession, viewSession } from '../api'
import { toast } from '../components/toast'
import { Button, Card, Modal, Notice, Segmented, Slider } from '../components/ui'
import { renderAnsi } from '../lib/ansi'
import { dateStamp, downloadBlob } from '../lib/download'
import { byName, median, quantile } from '../lib/format'
import { effectivePlayers } from '../store'
import { CONFIRMABLE_LABELS, unsavedKeys, useStore } from '../store'
import type { RoundGender, RoundType, SessionDocument } from '../types'
import { AdvancedDialog, PairsDialog, PlayerDialog } from './Dialogs'
import { FileHelp, PlayerImport } from './PlayerImport'

type AvailabilityMap = Record<string, boolean[]>
type AvailabilityChange = { playerId: string; round: number; previous: boolean; next: boolean }

function normalizeAvailability(availability: AvailabilityMap, selected: string[], rounds: number): AvailabilityMap {
  const out: AvailabilityMap = {}
  for (const playerId of selected) {
    const current = availability[playerId]
    const row = Array.isArray(current) ? current.slice(0, rounds).map(Boolean) : []
    while (row.length < rounds) row.push(true)
    out[playerId] = row
  }
  return out
}

function usePlayers() {
  const roster = useStore((s) => s.roster)
  const overrides = useStore((s) => s.overrides)
  return useMemo(() => effectivePlayers(roster, overrides), [roster, overrides])
}

function PlayersCard({ onEdit }: { onEdit: (id: string | null) => void }) {
  const players = usePlayers()
  const overrides = useStore((s) => s.overrides)
  const selected = useStore((s) => s.selected)
  const toggle = useStore((s) => s.toggleSelected)
  const setSelected = useStore((s) => s.setSelected)
  const [filter, setFilter] = useState('')
  const [replacing, setReplacing] = useState(false)
  const sorted = useMemo(() => [...players].sort(byName((p) => p.id)), [players])
  const visible = filter ? sorted.filter((p) => p.id.toLowerCase().includes(filter.toLowerCase())) : sorted

  return (
    <Card
      title="Available players"
      actions={
        <>
          <Button variant="ghost" className="min-h-8 py-1" onClick={() => setSelected(sorted.map((p) => p.id))}>
            Select all
          </Button>
          <Button variant="ghost" className="min-h-8 py-1" onClick={() => setSelected([])}>
            Clear
          </Button>
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-2">
        <input
          type="search"
          placeholder="Filter players"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="min-h-10 min-w-0 flex-1 rounded-lg border border-line bg-ink px-3 text-sm"
        />
        <Button onClick={() => onEdit(null)}>+ Add player</Button>
      </div>
      <div className="scroll-thin grid max-h-[46dvh] grid-cols-2 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-3 xl:grid-cols-4">
        {visible.map((p) => {
          const on = selected.includes(p.id)
          return (
            <div
              key={p.id}
              className={`flex min-h-11 items-stretch overflow-hidden rounded-lg border text-sm transition-colors ${on ? 'border-brand-yellow bg-brand-yellow text-black' : 'border-line bg-raised text-white'
                }`}
            >
              <button
                aria-pressed={on}
                onClick={() => toggle(p.id)}
                onContextMenu={(e) => {
                  e.preventDefault()
                  onEdit(p.id)
                }}
                className="min-w-0 flex-1 truncate px-1.5 text-left font-medium"
              >
                {p.id}
                {overrides[p.id] ? ' ✎' : ''}
              </button>
              <button
                aria-label={`Edit ${p.id}`}
                title="Edit specs"
                onClick={() => onEdit(p.id)}
                className={`px-1.5 text-xs ${on ? 'text-black/60 hover:text-black' : 'text-muted hover:text-white'}`}
              >
                ✎
              </button>
            </div>
          )
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
        <Button variant="ghost" onClick={() => setReplacing(true)}>
          Import players file
        </Button>
        <Button
          variant="ghost"
          onClick={async () => {
            try {
              downloadBlob(await exportPlayers(players), 'players.xlsx')
            } catch (e) {
              toast('error', (e as Error).message)
            }
          }}
        >
          Export players (.xlsx)
        </Button>
      </div>
      {replacing && (
        <Modal open title="Import players file" onClose={() => setReplacing(false)} wide>
          <Notice>Importing a file replaces the current player list and clears the edits made in this browser.</Notice>
          <div className="mt-3">
            <PlayerImport onImported={() => setReplacing(false)} />
          </div>
          <div className="mt-4">
            <FileHelp />
          </div>
        </Modal>
      )}
    </Card>
  )
}

function InfoCard({ availability, setAvailability }: { availability: AvailabilityMap; setAvailability: Dispatch<SetStateAction<AvailabilityMap>> }) {
  const players = usePlayers()
  const selected = useStore((s) => s.selected)
  const roundCount = useStore((s) => s.settings?.numRounds ?? 0)
  const byId = useMemo(() => new Map(players.map((p) => [p.id, p])), [players])
  const chosen = selected.map((id) => byId.get(id)).filter((p) => p !== undefined)
  const chosenSorted = useMemo(
    () => [...chosen].sort((a, b) => a.id.localeCompare(b.id, undefined, { sensitivity: 'base' })),
    [chosen],
  )
  const levels = chosen.map((p) => Number(p.Level)).sort((a, b) => a - b)
  const males = chosen.filter((p) => p.Gender === 'Male').length
  const q33 = quantile(levels, 0.33)
  const q66 = quantile(levels, 0.66)
  const count = (test: (level: number) => boolean) => levels.filter(test).length
  const mean = levels.reduce((a, b) => a + b, 0) / (levels.length || 1)
  const R = levels.length ? (quantile(levels, 0.9) - quantile(levels, 0.1)) : 0
  const [undoStack, setUndoStack] = useState<AvailabilityChange[][]>([])
  useEffect(() => {
    setUndoStack([])
  }, [selected.join('|'), roundCount])

  const applyAvailabilityChanges = (changes: AvailabilityChange[]) => {
    const effective = changes.filter((c) => c.previous !== c.next)
    if (!effective.length) return
    setAvailability((prev) => {
      const next = { ...prev }
      for (const c of effective) {
        const row = [...(next[c.playerId] ?? Array.from({ length: roundCount }, () => true))]
        while (row.length < roundCount) row.push(true)
        row[c.round] = c.next
        next[c.playerId] = row
      }
      return next
    })
    setUndoStack((stack) => [...stack, effective])
  }

  const setAll = (value: boolean) => {
    const changes: AvailabilityChange[] = []
    for (const p of chosenSorted) {
      const row = availability[p.id] ?? Array.from({ length: roundCount }, () => true)
      for (let r = 0; r < roundCount; r += 1) {
        const previous = row[r] ?? true
        changes.push({ playerId: p.id, round: r, previous, next: value })
      }
    }
    applyAvailabilityChanges(changes)
  }

  const setRoundIn = (round: number) => {
    const changes: AvailabilityChange[] = []
    for (const p of chosenSorted) {
      const row = availability[p.id] ?? Array.from({ length: roundCount }, () => true)
      const previous = row[round] ?? true
      changes.push({ playerId: p.id, round, previous, next: true })
    }
    applyAvailabilityChanges(changes)
  }

  const toggleCell = (playerId: string, round: number) => {
    const row = availability[playerId] ?? Array.from({ length: roundCount }, () => true)
    const previous = row[round] ?? true
    applyAvailabilityChanges([{ playerId, round, previous, next: !previous }])
  }

  const undo = () => {
    const frame = undoStack[undoStack.length - 1]
    if (!frame) return
    setAvailability((prev) => {
      const next = { ...prev }
      for (const c of frame) {
        const row = [...(next[c.playerId] ?? Array.from({ length: roundCount }, () => true))]
        while (row.length < roundCount) row.push(true)
        row[c.round] = c.previous
        next[c.playerId] = row
      }
      return next
    })
    setUndoStack((stack) => stack.slice(0, -1))
  }

  return (
    <Card title="Selected players info">
      {chosen.length === 0 ? (
        <p className="text-sm text-muted">No players selected</p>
      ) : (
        <div className="space-y-3 text-sm">
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              ['Players', chosen.length],
              ['Male', males],
              ['Female', chosen.length - males],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-ink/60 py-2">
                <div className="text-xl font-bold text-brand-yellow tabular-nums">{value}</div>
                <div className="text-xs text-muted">{label}</div>
              </div>
            ))}
          </div>
          <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1 text-soft">
            <dt>Lower third (≤ {q33.toFixed(2)})</dt>
            <dd className="tabular-nums">{count((l) => l <= q33)}</dd>
            <dt>
              Middle third ({q33.toFixed(2)} to {q66.toFixed(2)})
            </dt>
            <dd className="tabular-nums">{count((l) => l > q33 && l <= q66)}</dd>
            <dt>Upper third (&gt; {q66.toFixed(2)})</dt>
            <dd className="tabular-nums">{count((l) => l > q66)}</dd>
            <dt>Median level</dt>
            <dd className="tabular-nums">{median(levels).toFixed(2)}</dd>
            <dt>Average level</dt>
            <dd className="tabular-nums">{mean.toFixed(2)}</dd>
            <dt>Roster spread (R)</dt>
            <dd className="tabular-nums">{R.toFixed(2)}</dd>
          </dl>
          <div className="space-y-2 rounded-lg border border-line bg-ink/40 p-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-soft">Participation by round</p>
              <Button className="min-h-8 py-1" disabled={!undoStack.length} onClick={undo}>
                Undo
              </Button>
            </div>
            <div className="scroll-thin overflow-auto">
              <table className="min-w-full border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-30 border border-line bg-ink/95 px-2 py-1 text-left">
                      <div className="flex flex-col items-start gap-0.5">
                        <span className="leading-tight">Round<br /></span>
                        <div className="flex items-center gap-1">
                          <Button className="min-h-6 px-1 py-0 text-[9px] leading-none" onClick={() => setAll(true)}>All IN</Button>
                          {/* <Button className="min-h-6 px-1 py-0 text-[9px] leading-none" onClick={() => setAll(false)}>All OUT</Button> */}
                        </div>
                      </div>
                    </th>
                    {chosenSorted.map((p) => (
                      <th
                        key={p.id}
                        className="border border-line px-1 py-1 text-center align-bottom"
                        style={{ minWidth: `${Math.max(40, p.id.length * 8)}px` }}
                      >
                        <div className="relative mx-auto h-20 overflow-visible" style={{ width: `${Math.max(40, p.id.length * 8)}px` }}>
                          <span
                            className="absolute left-1/2 top-1/2 max-w-none -translate-x-1/2 -translate-y-1/2 origin-center -rotate-45 whitespace-nowrap font-semibold"
                            title={p.id}
                          >
                            {p.id}
                          </span>
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: roundCount }, (_, round) => (
                    <tr key={round}>
                      <td className="sticky left-0 z-20 border border-line bg-ink/95 px-2 py-1 font-semibold">
                        <Button className="min-h-7 py-0.5 px-2" onClick={() => setRoundIn(round)}>
                          R{round + 1} IN
                        </Button>
                      </td>
                      {chosenSorted.map((p) => {
                        const isIn = availability[p.id]?.[round] ?? true
                        return (
                          <td key={p.id} className="border border-line px-1 py-1 text-center">
                            <button
                              className={`min-h-7 min-w-10 rounded px-1 py-0.5 font-semibold ${isIn ? 'bg-[#1f7a3f] text-white' : 'bg-[#7f0301] text-white'}`}
                              onClick={() => toggleCell(p.id, round)}
                            >
                              {isIn ? 'IN' : 'OUT'}
                            </button>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}

function RoundsCard() {
  const settings = useStore((s) => s.settings)!
  const update = useStore((s) => s.updateSettings)
  const setRounds = useStore((s) => s.setRounds)

  return (
    <Card title="Round preferences">
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-soft">Rounds</span>
          <Button variant="danger" className="min-h-9 w-9 px-0" aria-label="Remove a round" onClick={() => setRounds(settings.numRounds - 1)}>
            −
          </Button>
          <span className="w-8 text-center text-lg font-bold text-brand-yellow tabular-nums">{settings.numRounds}</span>
          <Button variant="danger" className="min-h-9 w-9 px-0" aria-label="Add a round" onClick={() => setRounds(settings.numRounds + 1)}>
            +
          </Button>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-soft">Games per round</span>
          <select
            value={settings.gamesPerRound}
            onChange={(e) => update({ gamesPerRound: e.target.value })}
            className="min-h-9 rounded-lg border border-line bg-ink px-2"
          >
            <option value="auto">Auto</option>
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ol className="space-y-2">
        {settings.roundTypes.map((type, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 rounded-lg bg-ink/50 px-2.5 py-2">
            <span className="w-full text-sm font-semibold whitespace-nowrap sm:w-16">Round {i + 1}</span>
            <Segmented<RoundType>
              size="sm"
              label={`Round ${i + 1} type`}
              value={type}
              options={[
                { value: 'level', label: 'Level' },
                { value: 'balanced', label: 'Balanced' },
              ]}
              onChange={(v) => update({ roundTypes: settings.roundTypes.map((t, j) => (j === i ? v : t)) })}
            />
            <Segmented<RoundGender>
              size="sm"
              label={`Round ${i + 1} gender`}
              value={settings.roundGenders[i]}
              options={[
                { value: 'open', label: 'Open' },
                { value: 'mixed', label: 'Mixed' },
              ]}
              onChange={(v) => update({ roundGenders: settings.roundGenders.map((g, j) => (j === i ? v : g)) })}
            />
          </li>
        ))}
      </ol>
    </Card>
  )
}

function ParametersCard() {
  const settings = useStore((s) => s.settings)!
  const update = useStore((s) => s.updateSettings)
  const femaleShift = useStore((s) => s.femaleShift)
  const setFemaleShift = useStore((s) => s.setFemaleShift)
  const extraParameters = useStore((s) => s.extraParameters)
  const setExtraParameters = useStore((s) => s.setExtraParameters)
  const pairs = useStore((s) => s.pairs)
  const [dialog, setDialog] = useState<'pairs' | 'advanced' | null>(null)

  const levelRoundPlayPriority = (() => {
    const gameOptimization = extraParameters?.game_optimization
    if (!gameOptimization || typeof gameOptimization !== 'object' || Array.isArray(gameOptimization)) return 1
    const gamesByLevel = (gameOptimization as Record<string, unknown>).games_by_level
    if (!gamesByLevel || typeof gamesByLevel !== 'object' || Array.isArray(gamesByLevel)) return 1
    const notPlaying = (gamesByLevel as Record<string, unknown>).not_playing
    if (!notPlaying || typeof notPlaying !== 'object' || Array.isArray(notPlaying)) return 1
    const raw = (notPlaying as Record<string, unknown>).level_priority_strength
    return typeof raw === 'number' ? raw : 1
  })()

  const setLevelRoundPlayPriority = (value: number) => {
    const root = (extraParameters && typeof extraParameters === 'object' && !Array.isArray(extraParameters)) ? extraParameters : {}
    const gameOptimization = (root.game_optimization && typeof root.game_optimization === 'object' && !Array.isArray(root.game_optimization)) ? (root.game_optimization as Record<string, unknown>) : {}
    const gamesByLevel = (gameOptimization.games_by_level && typeof gameOptimization.games_by_level === 'object' && !Array.isArray(gameOptimization.games_by_level)) ? (gameOptimization.games_by_level as Record<string, unknown>) : {}
    const notPlaying = (gamesByLevel.not_playing && typeof gamesByLevel.not_playing === 'object' && !Array.isArray(gamesByLevel.not_playing)) ? (gamesByLevel.not_playing as Record<string, unknown>) : {}

    setExtraParameters({
      ...root,
      game_optimization: {
        ...gameOptimization,
        games_by_level: {
          ...gamesByLevel,
          not_playing: {
            ...notPlaying,
            level_priority_strength: value,
          },
        },
      },
    })
  }

  return (
    <Card title="Parameters">
      <div className="grid gap-2 sm:grid-cols-2">
        <Slider
          label={`Factor for bottom ${settings.percentile}%`}
          help="Higher values prioritize increasing the happiness of the bottom x% of players."
          value={settings.lambdaWeight}
          min={0}
          max={10}
          step={0.1}
          onChange={(v) => update({ lambdaWeight: v })}
        />
        <Slider
          label="Bottom x% size"
          help="Percentile threshold x used to define the bottom x% of players by happiness."
          value={settings.percentile}
          min={0}
          max={50}
          step={1}
          onChange={(v) => update({ percentile: v })}
        />
        <Slider
          label="Maximal level gap in game"
          help="Maximum allowed level difference considered acceptable inside a game."
          value={settings.levelGapTol}
          min={0.5}
          max={3}
          step={0.1}
          onChange={(v) => update({ levelGapTol: v })}
        />
        <Slider
          label="Shift female levels"
          help="Temporary shift applied to female players' level before matchmaking."
          value={femaleShift}
          min={-2}
          max={2}
          step={0.1}
          format={(v) => (v > 0 ? '+' : '') + v.toFixed(1)}
          onChange={setFemaleShift}
        />
        <Slider
          label="Level-round play priority"
          help="Higher values keep stronger players active more aggressively in level rounds. In level + mixed rounds, this also keeps stronger players active within each gender when possible."
          value={levelRoundPlayPriority}
          min={0}
          max={2}
          step={0.1}
          onChange={setLevelRoundPlayPriority}
        />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-sm" title="Enable or disable spectrum preferences during matchup generation.">
          <span className="text-soft">Spectrum</span>
          <Segmented
            size="sm"
            value={settings.spectrum ? 'on' : 'off'}
            options={[
              { value: 'on', label: 'ON' },
              { value: 'off', label: 'OFF' },
            ]}
            onChange={(v) => update({ spectrum: v === 'on' })}
          />
        </div>
        <Button variant="danger" onClick={() => setDialog('pairs')}>
          👥 Preferred pairs{pairs.length ? ` · ${pairs.length} pair${pairs.length > 1 ? 's' : ''}` : ''}
        </Button>
        <Button variant="ghost" onClick={() => setDialog('advanced')}>
          Advanced…
        </Button>
      </div>
      {dialog === 'pairs' && <PairsDialog onClose={() => setDialog(null)} />}
      {dialog === 'advanced' && <AdvancedDialog onClose={() => setDialog(null)} />}
    </Card>
  )
}

function UnsavedBanner() {
  const state = useStore()
  const keys = unsavedKeys(state)
  if (!keys.length) return null
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-brand-yellow/40 bg-brand-yellow/10 px-4 py-2.5 text-sm">
      <span className="w-full sm:w-auto sm:flex-1">
        Not saved as default: <strong>{keys.map((k) => CONFIRMABLE_LABELS[k]).join(', ')}</strong>
      </span>
      <Button variant="ghost" className="min-h-8 py-1" onClick={() => state.discardConfirmable(keys)}>
        Discard
      </Button>
      <Button variant="primary" className="min-h-8 py-1" onClick={() => state.saveConfirmable(keys)}>
        Save as default
      </Button>
    </div>
  )
}

function ConsoleCard() {
  const text = useStore((s) => s.consoleText)
  const clear = useStore((s) => s.clearConsole)
  const ref = useRef<HTMLPreElement>(null)
  const rendered = useMemo(() => renderAnsi(text), [text])
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [text])
  return (
    <Card
      title="Console output"
      actions={
        <Button variant="ghost" className="min-h-8 py-1" onClick={clear} disabled={!text}>
          Clear
        </Button>
      }
    >
      <pre ref={ref} className="scroll-thin h-72 overflow-auto rounded-lg bg-[#1e1e1e] p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-[#d4d4d4]">
        {text ? rendered : 'Console output will appear here...'}
      </pre>
    </Card>
  )
}

function RunBar({ availability }: { availability: AvailabilityMap }) {
  const players = usePlayers()
  const state = useStore()
  const [progress, setProgress] = useState<{ seed: number; first: number; last: number } | null>(null)
  const [running, setRunning] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const openDocument = async (document: SessionDocument, label: string, remember = true) => {
    const view = await viewSession(document)
    state.openSession(document, view, label, remember)
    state.setTab('editor')
  }

  const run = async () => {
    const s = useStore.getState()
    const settings = s.settings!
    const byId = new Map(players.map((p) => [p.id, p]))
    const chosen = s.selected.map((id) => byId.get(id)).filter((p) => p !== undefined)
    if (chosen.length < 4) {
      toast('error', 'Please select at least 4 players to run a session.')
      return
    }
    setRunning(true)
    setProgress(null)
    s.clearConsole()
    try {
      await generateSession(
        {
          players: chosen,
          availability: Object.fromEntries(
            chosen.map((p) => {
              const row = availability[p.id]
              const normalized = Array.isArray(row) && row.length === settings.numRounds
                ? row.map(Boolean)
                : Array.from({ length: settings.numRounds }, () => true)
              return [p.id, normalized]
            }),
          ),
          amount_of_rounds: settings.numRounds,
          type_preferences: settings.roundTypes,
          gender_preferences: settings.roundGenders,
          games_per_round: settings.gamesPerRound === 'auto' ? null : Number(settings.gamesPerRound),
          level_gap_tol: settings.levelGapTol,
          lambda_weight: settings.lambdaWeight,
          percentile: settings.percentile,
          female_shift: s.femaleShift,
          spectrum: settings.spectrum,
          preferred_pairs: s.pairs.filter((p) => p.players.every((id) => s.selected.includes(id))),
          extra_parameters: s.extraParameters ?? {},
        },
        (event) => {
          if (event.type === 'log') useStore.getState().appendConsole(event.text)
          if (event.type === 'progress') setProgress(event)
          if (event.type === 'error') throw new Error(event.message)
          if (event.type === 'result') {
            useStore.getState().openSession(event.document, event.view, `Session of ${dateStamp().replaceAll('_', '/')}`)
            useStore.getState().setTab('editor')
            toast('success', `Session generated (seed ${event.document.seed}).`)
          }
        },
      )
    } catch (e) {
      toast('error', `An error occurred:\n${(e as Error).message}`)
    } finally {
      setRunning(false)
    }
  }

  const total = progress ? progress.last - progress.first + 1 : 0
  const done = progress ? progress.seed - progress.first + 1 : 0

  return (
    <>
      <div className="pb-safe sticky bottom-16 z-20 -mx-3 border-t border-line bg-ink/95 px-3 py-3 backdrop-blur sm:-mx-4 sm:px-4 md:bottom-0">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" className="min-h-12 flex-1 text-base sm:flex-none sm:px-8" disabled={running} onClick={run}>
            ⚡ Run session generation
          </Button>
          <Button variant="subtle" className="min-h-12" onClick={() => fileRef.current?.click()}>
            📂 Load session
          </Button>
          <span className="text-sm text-muted">{state.selected.length} selected</span>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="sr-only"
            onChange={async (e) => {
              const file = e.target.files?.[0]
              e.target.value = ''
              if (!file) return
              try {
                await openDocument(JSON.parse(await file.text()), file.name)
                toast('success', `Session loaded from ${file.name}.`)
              } catch (err) {
                toast('error', `Could not load session:\n${(err as Error).message}`)
              }
            }}
          />
        </div>
        {state.recent.length > 0 && (
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer text-muted">Recent sessions in this browser</summary>
            <ul className="mt-2 flex flex-wrap gap-2">
              {state.recent.map((r) => (
                <li key={r.savedAt}>
                  <Button
                    variant="ghost"
                    className="min-h-8 py-1"
                    onClick={() => openDocument(r.document, r.label, false).catch((e: Error) => toast('error', e.message))}
                  >
                    {r.label} · {new Date(r.savedAt).toLocaleString()}
                  </Button>
                </li>
              ))}
              <li>
                <Button variant="ghost" className="min-h-8 py-1 text-muted" onClick={state.clearRecent}>
                  Forget recent sessions
                </Button>
              </li>
            </ul>
          </details>
        )}
      </div>
      <Modal open={running} title="⚡ Generating session" onClose={() => undefined}>
        <p className="text-sm text-soft">{progress ? `Testing seed ${progress.seed} of ${progress.last}...` : 'Starting...'}</p>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-ink">
          <div className="h-full rounded-full bg-brand-yellow transition-all" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
        </div>
        <p className="mt-2 text-right font-semibold text-brand-yellow tabular-nums">{total ? Math.round((done / total) * 100) : 0}%</p>
      </Modal>
    </>
  )
}

export function GenerateScreen() {
  const roster = useStore((s) => s.roster)
  const selected = useStore((s) => s.selected)
  const numRounds = useStore((s) => s.settings?.numRounds ?? 0)
  const availability = useStore((s) => s.generationAvailability)
  const setAvailability = useStore((s) => s.setGenerationAvailability)
  const [editing, setEditing] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    setAvailability((prev) => normalizeAvailability(prev, selected, numRounds))
  }, [selected, numRounds, setAvailability])

  if (roster.length === 0) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Card title="⚡ First-time setup">
          <p className="mb-4 text-sm text-soft">
            Import your players Excel file. The players stay in this browser: nothing is stored on the server.
          </p>
          <PlayerImport />
          <div className="mt-5 border-t border-line pt-4">
            <FileHelp />
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <UnsavedBanner />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,2.8fr)]">
        <PlayersCard onEdit={setEditing} />
        <InfoCard availability={availability} setAvailability={setAvailability} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <RoundsCard />
        <ParametersCard />
      </div>
      <ConsoleCard />
      <RunBar availability={availability} />
      {editing !== undefined && <PlayerDialog playerId={editing} onClose={() => setEditing(undefined)} />}
    </div>
  )
}
