import { useState } from 'react'
import { parsePlayers } from '../api'
import { toast } from '../components/toast'
import { Button, Modal, Notice } from '../components/ui'
import { SPEC_HELP } from '../lib/format'
import { useStore } from '../store'
import { SPECTRUM, type Gender, type Player } from '../types'

const EXAMPLE = [
  ['Alice', 'Martin', 'Female', '3.0', '5', '4', '3', '2', '1', '5'],
  ['Bob', 'Dupont', 'Male', '3.5', '', '', '', '', '', ''],
  ['Clara', 'Bernard', 'Female', '2.0', '2', '5', '4', '3', '5', '1'],
]

export function FileHelp() {
  return (
    <div className="space-y-3 text-sm text-soft">
      <div>
        <p className="font-medium text-white">Required columns</p>
        <ul className="mt-1 list-inside list-disc space-y-0.5 text-muted">
          <li>Name (or "Prénom")</li>
          <li>Surname (or "Nom")</li>
          <li>Gender: "Male" or "Female" ("Masculin" or "Féminin")</li>
          <li>Level: a number, e.g. 1.0 to 5.0</li>
        </ul>
      </div>
      <div>
        <p className="font-medium text-white">Optional spectrum columns (scores 0 to 5, blank means 5)</p>
        <ul className="mt-1 space-y-1">
          {SPECTRUM.map((s) => (
            <li key={s}>
              <span className="font-semibold text-brand-yellow">{s}</span>
              <span className="text-muted">: {SPEC_HELP[s]}</span>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-muted">Players with missing gender or level are asked for right after the import.</p>
      <div className="scroll-thin overflow-x-auto rounded-lg border border-line">
        <table className="w-full font-mono text-xs">
          <thead className="bg-raised text-left">
            <tr>
              {['Name', 'Surname', 'Gender', 'Level', ...SPECTRUM].map((h) => (
                <th key={h} className="px-2 py-1.5 font-semibold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {EXAMPLE.map((row) => (
              <tr key={row[0]} className="border-t border-line">
                {row.map((cell, i) => (
                  <td key={i} className="px-2 py-1">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function MissingValues({ players, onDone, onCancel }: { players: Player[]; onDone: (players: Player[]) => void; onCancel: () => void }) {
  const missing = players.filter((p) => !p.Gender || p.Level === null)
  const [values, setValues] = useState<Record<string, { gender: Gender; level: string }>>(() =>
    Object.fromEntries(missing.map((p) => [p.id, { gender: p.Gender ?? 'Female', level: p.Level === null ? '' : String(p.Level) }])),
  )
  const [error, setError] = useState<string | null>(null)

  const save = () => {
    for (const p of missing) {
      const level = Number(values[p.id].level)
      if (p.Level === null && (!values[p.id].level || !Number.isFinite(level) || level < 0.5 || level > 6)) {
        setError(`Invalid level for ${p.id}: enter a number between 0.5 and 6.0`)
        return
      }
    }
    onDone(
      players.map((p) =>
        values[p.id]
          ? { ...p, Gender: p.Gender ?? values[p.id].gender, Level: p.Level ?? Number(values[p.id].level) }
          : p,
      ),
    )
  }

  return (
    <Modal
      open
      title="⚠ Complete missing player data"
      onClose={onCancel}
      footer={
        <Button variant="primary" onClick={save}>
          Save & continue
        </Button>
      }
    >
      <p className="mb-3 text-sm text-soft">Some players have a missing gender or level. Please fill them in:</p>
      {error && <Notice tone="error">{error}</Notice>}
      <ul className="mt-3 space-y-2">
        {missing.map((p) => (
          <li key={p.id} className="rounded-lg border border-line bg-ink/60 p-3">
            <p className="font-semibold text-brand-yellow">{p.id}</p>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm">
              {!p.Gender && (
                <fieldset className="flex items-center gap-3">
                  <legend className="sr-only">Gender</legend>
                  <span className="text-muted">Gender:</span>
                  {(['Male', 'Female'] as const).map((g) => (
                    <label key={g} className="flex items-center gap-1.5">
                      <input
                        type="radio"
                        checked={values[p.id].gender === g}
                        onChange={() => setValues((v) => ({ ...v, [p.id]: { ...v[p.id], gender: g } }))}
                      />
                      {g}
                    </label>
                  ))}
                </fieldset>
              )}
              {p.Level === null && (
                <label className="flex items-center gap-2">
                  <span className="text-muted">Level:</span>
                  <input
                    inputMode="decimal"
                    className="w-20 rounded-md border border-line bg-raised px-2 py-1"
                    value={values[p.id].level}
                    onChange={(e) => setValues((v) => ({ ...v, [p.id]: { ...v[p.id], level: e.target.value } }))}
                  />
                  <span className="text-xs text-muted">(1.0 to 5.0)</span>
                </label>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Modal>
  )
}

/** Choose a players xlsx, validate it on the server, then fill missing values. */
export function PlayerImport({ onImported }: { onImported?: () => void }) {
  const setRoster = useStore((s) => s.setRoster)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<string[]>([])
  const [pending, setPending] = useState<Player[] | null>(null)

  const finish = (players: Player[]) => {
    setRoster(players)
    setPending(null)
    toast('success', `${players.length} players imported. They are stored in this browser.`)
    onImported?.()
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setErrors([])
    try {
      const result = await parsePlayers(file)
      if (result.errors.length || !result.players) {
        setErrors(result.errors)
      } else if (result.players.some((p) => !p.Gender || p.Level === null)) {
        setPending(result.players)
      } else {
        finish(result.players)
      }
    } catch (e) {
      setErrors([(e as Error).message])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-3">
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-line bg-ink/50 px-4 py-6 text-center hover:border-brand-yellow">
        <span className="text-sm font-semibold text-brand-yellow">{busy ? 'Reading file…' : 'Choose a players Excel file'}</span>
        <span className="text-xs text-muted">.xlsx or .xls</span>
        <input type="file" accept=".xlsx,.xls" className="sr-only" disabled={busy} onChange={(e) => onFile(e.target.files?.[0])} />
      </label>
      {errors.length > 0 && (
        <Notice tone="error">
          <ul className="list-inside list-disc">
            {errors.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </Notice>
      )}
      {pending && <MissingValues players={pending} onDone={finish} onCancel={() => setPending(null)} />}
    </div>
  )
}
