import { useMemo, useState } from 'react'
import { toast } from '../components/toast'
import { Button, Modal, Notice, Segmented } from '../components/ui'
import { byName, SPEC_HELP } from '../lib/format'
import { downloadJson } from '../lib/download'
import { effectivePlayers, useStore } from '../store'
import { SPECTRUM, type Gender, type Player, type PreferredPair } from '../types'

/** Same normalisation as the xlsx import: no whitespace, first letter upper case. */
const normaliseName = (value: string) => {
  const compact = value.replace(/\s+/g, '')
  return compact.charAt(0).toUpperCase() + compact.slice(1).toLowerCase()
}

export function PlayerDialog({ playerId, onClose }: { playerId: string | null; onClose: () => void }) {
  const roster = useStore((s) => s.roster)
  const overrides = useStore((s) => s.overrides)
  const upsertPlayer = useStore((s) => s.upsertPlayer)
  const setOverride = useStore((s) => s.setOverride)
  const base = playerId ? roster.find((p) => p.id === playerId) : undefined
  const initial = (source?: Player): Player => ({
    id: source?.id ?? '',
    Name: source?.Name ?? '',
    Surname: source?.Surname ?? '',
    Gender: source?.Gender === 'Female' ? 'Female' : 'Male',
    Level: source?.Level ?? 1.5,
    ...(Object.fromEntries(SPECTRUM.map((s) => [s, source?.[s] ?? 5])) as Record<(typeof SPECTRUM)[number], number>),
  })
  const [form, setForm] = useState<Player>(() => initial(base && { ...base, ...overrides[base.id] }))
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const save = () => {
    const level = Number(form.Level)
    if (!Number.isFinite(level) || SPECTRUM.some((s) => !Number.isFinite(Number(form[s])))) {
      setError('Level and spectrum values must be numeric.')
      return
    }
    const values = { ...form, Level: level, ...Object.fromEntries(SPECTRUM.map((s) => [s, Number(form[s])])) }
    if (base) {
      const { Gender, Level, ...rest } = values
      setOverride(base.id, { Gender, Level, ...Object.fromEntries(SPECTRUM.map((s) => [s, rest[s]])) })
    } else {
      const id = normaliseName(name)
      if (!id) {
        setError('Please enter a player name.')
        return
      }
      if (roster.some((p) => p.id === id)) {
        setError(`Player '${id}' already exists.`)
        return
      }
      upsertPlayer({ ...values, id, Name: id, Surname: '' })
      toast('success', `${id} added and selected.`)
    }
    onClose()
  }

  const numberField = (key: 'Level' | (typeof SPECTRUM)[number], min: number, max: number, step: number) => (
    <input
      type="number"
      inputMode="decimal"
      min={min}
      max={max}
      step={step}
      value={form[key] ?? ''}
      onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value === '' ? null : Number(e.target.value) }))}
      className="w-full rounded-md border border-line bg-raised px-2 py-1.5"
    />
  )

  return (
    <Modal
      open
      title={base ? `Edit ${base.id}` : 'Add new player'}
      onClose={onClose}
      footer={
        <>
          {base && overrides[base.id] && (
            <Button
              variant="danger"
              onClick={() => {
                setOverride(base.id, null)
                setForm(initial(base))
              }}
            >
              Reset
            </Button>
          )}
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save}>
            {base ? 'Save' : 'Add player'}
          </Button>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault()
          save()
        }}
      >
        {error && <Notice tone="error">{error}</Notice>}
        {base ? (
          <p className="text-sm text-muted">
            Edits apply to this browser only and can be reset at any time. The original values come from the imported file.
          </p>
        ) : (
          <label className="block text-sm">
            <span className="text-soft">Name</span>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded-md border border-line bg-raised px-2 py-1.5"
            />
          </label>
        )}
        <div className="flex flex-wrap items-end gap-4">
          <div className="text-sm">
            <span className="mb-1 block text-soft">Gender</span>
            <Segmented
              value={form.Gender ?? 'Male'}
              options={[
                { value: 'Male', label: 'Male' },
                { value: 'Female', label: 'Female' },
              ]}
              onChange={(g: Gender) => setForm((f) => ({ ...f, Gender: g }))}
            />
          </div>
          <label className="w-28 text-sm">
            <span className="mb-1 block text-soft">Level</span>
            {numberField('Level', 0, 10000, 0.1)}
          </label>
        </div>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-brand-yellow">Spectrum attributes</legend>
          <div className="grid grid-cols-2 gap-3">
            {SPECTRUM.map((s) => (
              <label key={s} className="text-sm" title={SPEC_HELP[s]}>
                <span className="mb-1 block text-soft">{s}</span>
                {numberField(s, 0, 10, 1)}
              </label>
            ))}
          </div>
        </fieldset>
        <button type="submit" className="hidden" />
      </form>
    </Modal>
  )
}

const PAIR_COLORS = ['bg-[#4CAF50]', 'bg-[#2E7D32]', 'bg-[#1B5E20]', 'bg-[#004D40]']

export function PairsDialog({ onClose }: { onClose: () => void }) {
  const roster = useStore((s) => s.roster)
  const selected = useStore((s) => s.selected)
  const pairs = useStore((s) => s.pairs)
  const setPairs = useStore((s) => s.setPairs)
  const [working, setWorking] = useState<PreferredPair[]>(pairs)
  const [pending, setPending] = useState<string[]>([])
  const sorted = useMemo(() => [...roster].sort(byName((p) => p.id)), [roster])
  const inPair = new Set(working.flatMap((p) => p.players))
  const candidate = pending.length === 2 ? [...pending].sort() : null
  const canAdd = candidate && !working.some((p) => p.players[0] === candidate[0] && p.players[1] === candidate[1])

  const close = () => {
    setPairs(working)
    onClose()
  }

  return (
    <Modal
      open
      wide
      title="👥 Preferred pairs"
      onClose={close}
      footer={
        <>
          {[1, 2, 3, 4].map((n) => (
            <button
              key={n}
              disabled={!canAdd}
              onClick={() => {
                setWorking((w) => [...w, { players: candidate as [string, string], games: n }])
                setPending([])
              }}
              className={`min-h-10 rounded-lg px-3 text-sm font-semibold text-white disabled:opacity-35 ${PAIR_COLORS[n - 1]}`}
            >
              Add pair · {n} game{n > 1 ? 's' : ''}
            </button>
          ))}
          <Button variant="danger" disabled={!working.length} onClick={() => setWorking((w) => w.slice(0, -1))}>
            Remove last pair
          </Button>
          <Button variant="primary" onClick={close}>
            Confirm
          </Button>
        </>
      }
    >
      <p className="mb-3 text-sm text-soft">Tap two players, then choose how many games to force them together.</p>
      <section className="mb-4 rounded-lg border border-line bg-ink/60 p-3">
        <h3 className="mb-1 text-xs font-semibold tracking-wide text-brand-yellow uppercase">Current pairs</h3>
        {working.length ? (
          <ol className="space-y-1 text-sm">
            {working.map((p, i) => (
              <li key={p.players.join('/') + i} className="flex items-center justify-between gap-2">
                <span>
                  {i + 1}. {p.players[0]} / {p.players[1]}
                </span>
                <span className="flex items-center gap-2 text-muted">
                  {p.games} game{p.games > 1 ? 's' : ''}
                  <button aria-label="Remove pair" className="px-1 text-loss" onClick={() => setWorking((w) => w.filter((_, j) => j !== i))}>
                    ×
                  </button>
                </span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-sm text-muted">(none)</p>
        )}
      </section>
      <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4 lg:grid-cols-6">
        {sorted.map((p) => {
          const isPending = pending.includes(p.id)
          const isSelected = selected.includes(p.id)
          return (
            <button
              key={p.id}
              onClick={() =>
                setPending((list) => (list.includes(p.id) ? list.filter((x) => x !== p.id) : [...list, p.id].slice(-2)))
              }
              className={`min-h-10 truncate rounded-md border px-2 text-sm ${
                isPending
                  ? 'border-brand-yellow bg-brand-yellow text-black'
                  : inPair.has(p.id)
                    ? 'border-[#8B3030] bg-[#8B3030] text-white'
                    : isSelected
                      ? 'border-line bg-white text-black'
                      : 'border-line bg-raised text-muted'
              } ${isSelected ? 'font-semibold' : ''}`}
            >
              {p.id}
            </button>
          )
        })}
      </div>
    </Modal>
  )
}

export function AdvancedDialog({ onClose }: { onClose: () => void }) {
  const extra = useStore((s) => s.extraParameters)
  const defaults = useStore((s) => s.extraDefaults)
  const setExtra = useStore((s) => s.setExtraParameters)
  const [text, setText] = useState(() => JSON.stringify(extra, null, 2))
  const [error, setError] = useState<string | null>(null)

  const save = () => {
    try {
      const value = JSON.parse(text)
      if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('Expected a JSON object.')
      setExtra(value)
      toast('success', 'Advanced parameters saved.')
      onClose()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <Modal
      open
      wide
      title="Advanced parameters"
      onClose={onClose}
      footer={
        <>
          <label className="inline-flex min-h-10 cursor-pointer items-center rounded-lg border border-line px-3.5 text-sm text-soft hover:bg-raised">
            Import JSON
            <input
              type="file"
              accept=".json,application/json"
              className="sr-only"
              onChange={async (e) => {
                const file = e.target.files?.[0]
                if (file) setText(await file.text())
              }}
            />
          </label>
          <Button
            variant="ghost"
            onClick={() => {
              try {
                downloadJson(JSON.parse(text), 'extra_parameters.json')
              } catch (e) {
                setError((e as Error).message)
              }
            }}
          >
            Download
          </Button>
          <Button variant="ghost" onClick={() => setText(JSON.stringify(defaults, null, 2))}>
            Reset to defaults
          </Button>
          <Button variant="primary" onClick={save}>
            Save
          </Button>
        </>
      }
    >
      <p className="mb-3 text-sm text-soft">
        Generation knobs of <code>extra_parameters.json</code>: seed range, iteration budget, penalties, bonuses and spectrum thresholds.
      </p>
      {error && <Notice tone="error">{error}</Notice>}
      <textarea
        spellCheck={false}
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setError(null)
        }}
        className="scroll-thin mt-2 h-[55dvh] w-full rounded-lg border border-line bg-[#1e1e1e] p-3 font-mono text-xs text-[#d4d4d4]"
      />
    </Modal>
  )
}

export function usePlayers() {
  const roster = useStore((s) => s.roster)
  const overrides = useStore((s) => s.overrides)
  return useMemo(() => effectivePlayers(roster, overrides), [roster, overrides])
}
