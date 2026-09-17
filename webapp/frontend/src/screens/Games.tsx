import { useState } from 'react'
import { sessionPng, sessionReport, sessionXlsx, viewSession } from '../api'
import { toast } from '../components/toast'
import { Button, Card, Modal, Segmented } from '../components/ui'
import { dateStamp, downloadBlob, downloadJson } from '../lib/download'
import { ROUND_ABBREV } from '../lib/format'
import { useStore } from '../store'
import type { RoundDoc } from '../types'

const diffColor = (d: number) => (d <= 0.3 ? 'text-[#1A6B2A]' : d <= 0.8 ? 'text-[#9B4400]' : 'text-[#8B0000]')

function RoundTable({ round, index, levels, showLevels }: { round: RoundDoc; index: number; levels: Map<string, number>; showLevels: boolean }) {
  const mean = (team: string[]) => team.reduce((s, n) => s + (levels.get(n) ?? 0), 0) / team.length
  const tag = [ROUND_ABBREV[round.type_preference], ROUND_ABBREV[round.gender_preference]].filter(Boolean).join(' / ')
  const name = (n: string) => (
    <span className="block min-w-0 truncate">
      {n}
      {showLevels && <span className="block text-[11px] opacity-75">{levels.get(n)?.toFixed(1)}</span>}
    </span>
  )
  return (
    <div className="overflow-hidden rounded-lg bg-white text-[#333] shadow">
      <div className="bg-round-title px-3 py-1.5 text-sm font-bold text-white">
        ROUND {index + 1}
        <span className="ml-3 font-normal opacity-85">[{tag}]</span>
      </div>
      <div className="grid grid-cols-[1.75rem_1fr_2rem_1fr_3.25rem] bg-round-header text-[11px] font-bold text-white">
        <span className="px-1 py-1 text-center">#</span>
        <span className="px-2 py-1">Team 1</span>
        <span className="py-1 text-center">VS</span>
        <span className="px-2 py-1">Team 2</span>
        <span className="py-1 text-center">Δ</span>
      </div>
      {round.games.map((g, i) => {
        const diff = Math.abs(mean(g.team_a) - mean(g.team_b))
        return (
          <div key={i} className={`grid grid-cols-[1.75rem_1fr_2rem_1fr_3.25rem] items-stretch border-t border-[#B8B8B8] text-sm ${i % 2 ? 'bg-[#F2F7FF]' : 'bg-white'}`}>
            <span className="flex items-center justify-center text-xs">{i + 1}</span>
            <span className="grid grid-cols-1 gap-px bg-team-a text-team-a-ink sm:grid-cols-2">
              {g.team_a.map((n) => (
                <span key={n} className="px-2 py-1">
                  {name(n)}
                </span>
              ))}
            </span>
            <span className="flex items-center justify-center bg-[#E7E6E6] text-xs font-bold">VS</span>
            <span className="grid grid-cols-1 gap-px bg-team-b text-team-b-ink sm:grid-cols-2">
              {g.team_b.map((n) => (
                <span key={n} className="px-2 py-1">
                  {name(n)}
                </span>
              ))}
            </span>
            <span className={`flex items-center justify-center bg-[#FFF2CC] font-mono text-xs font-bold ${diffColor(diff)}`}>{diff.toFixed(2)}</span>
          </div>
        )
      })}
      {round.bench.length > 0 && (
        <div className="border-t border-[#B8B8B8] bg-bench px-3 py-1.5 text-xs">
          <span className="font-semibold">Not playing:</span> {round.bench.join(', ')}
        </div>
      )}
    </div>
  )
}

export function GamesScreen() {
  const document = useStore((s) => s.document)!
  const commit = useStore((s) => s.commitSession)
  const pendingSwaps = useStore((s) => s.pendingSwaps)
  const showLevels = useStore((s) => s.showLevels)
  const setShowLevels = useStore((s) => s.setShowLevels)
  const [order, setOrder] = useState(() => document.rounds.map((_, i) => i))
  const [picked, setPicked] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)
  const levels = new Map(document.players.map((p) => [p.id, Number(p.Level)]))
  const identity = order.length === document.rounds.length ? order : document.rounds.map((_, i) => i)
  const outOfPlace = identity.filter((v, i) => v !== i).length

  const tap = (position: number) => {
    if (picked === null) setPicked(position)
    else if (picked === position) setPicked(null)
    else {
      const next = [...identity]
      ;[next[picked], next[position]] = [next[position], next[picked]]
      setOrder(next)
      setPicked(null)
    }
  }

  const applyOrder = async () => {
    setConfirming(false)
    setBusy('apply')
    try {
      const reordered = { ...document, rounds: identity.map((i) => document.rounds[i]) }
      const view = await viewSession(reordered)
      commit(reordered, view, view.summary.score)
      setOrder(reordered.rounds.map((_, i) => i))
      toast('success', `Round order applied: ${identity.map((i) => `R${i + 1}`).join(' → ')}`)
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const download = async (kind: string, run: () => Promise<void>) => {
    setBusy(kind)
    try {
      await run()
    } catch (e) {
      toast('error', (e as Error).message)
    } finally {
      setBusy(null)
    }
  }
  const stamp = dateStamp()

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="space-y-3">
        <h2 className="text-xl font-bold text-brand-yellow">Session games</h2>
        <p className="text-sm text-soft">Tap a round to select it, then tap another one to swap their order.</p>
        {identity.map((roundIndex, position) => (
          <button
            key={roundIndex}
            onClick={() => tap(position)}
            className={`block w-full rounded-xl p-1 text-left transition ${picked === position ? 'bg-brand-yellow' : 'bg-transparent hover:bg-raised'}`}
            aria-pressed={picked === position}
          >
            <RoundTable round={document.rounds[roundIndex]} index={position} levels={levels} showLevels={showLevels} />
            {roundIndex !== position && <span className="mt-1 block px-1 text-xs text-brand-yellow">Was round {roundIndex + 1}</span>}
          </button>
        ))}
      </div>

      <aside className="order-first space-y-4 lg:sticky lg:top-20 lg:order-none lg:self-start">
        <Card title="Round order">
          <p className={`mb-3 text-sm ${outOfPlace ? 'text-brand-yellow' : 'text-muted'}`}>
            {outOfPlace ? `${outOfPlace} round(s) out of place` : 'No pending modifications'}
          </p>
          <div className="mb-3 flex items-center gap-2 text-sm">
            <span className="text-soft">Show levels</span>
            <Segmented
              size="sm"
              value={showLevels ? 'on' : 'off'}
              options={[
                { value: 'on', label: 'ON' },
                { value: 'off', label: 'OFF' },
              ]}
              onChange={(v) => setShowLevels(v === 'on')}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={!outOfPlace || busy !== null} onClick={() => (pendingSwaps.length ? setConfirming(true) : applyOrder())}>
              Apply changes
            </Button>
            <Button disabled={!outOfPlace} onClick={() => setOrder(document.rounds.map((_, i) => i))}>
              Reset order
            </Button>
          </div>
        </Card>
        <Card title="Downloads">
          <div className="grid gap-2">
            <Button disabled={busy !== null} onClick={() => download('png', async () => downloadBlob(await sessionPng(document, showLevels), 'session_games.png'))}>
              Session games image (.png)
            </Button>
            <Button disabled={busy !== null} onClick={() => download('xlsx', async () => downloadBlob(await sessionXlsx(document, false), `session_${stamp}.xlsx`))}>
              Excel file (.xlsx)
            </Button>
            <Button disabled={busy !== null} onClick={() => download('ro', async () => downloadBlob(await sessionXlsx(document, true), `session_${stamp}_read_only.xlsx`))}>
              Read-only Excel file
            </Button>
            <Button onClick={() => downloadJson(document, `session_${stamp}.json`)}>Session file (.json)</Button>
            <Button
              disabled={busy !== null}
              onClick={() =>
                download('report', async () => {
                  const { text } = await sessionReport(document)
                  downloadBlob(new Blob([text.replace(/\x1b\[[\d;]*m/g, '')], { type: 'text/plain' }), `session_${stamp}_report.txt`)
                })
              }
            >
              Text report (.txt)
            </Button>
          </div>
          {busy && <p className="mt-2 text-xs text-muted">Preparing…</p>}
          <p className="mt-3 text-xs text-muted">The .json session file can be loaded again from the Session tab.</p>
        </Card>
      </aside>

      <Modal
        open={confirming}
        title="Pending games editor changes"
        onClose={() => setConfirming(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={applyOrder}>
              Continue
            </Button>
          </>
        }
      >
        <p className="text-sm">The games editor has unapplied player swaps. Applying the round swap will discard them.</p>
      </Modal>
    </div>
  )
}
