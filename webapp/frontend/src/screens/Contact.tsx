import { toast } from '../components/toast'
import { Button, Card } from '../components/ui'
import { downloadJson } from '../lib/download'
import { useStore } from '../store'
import type { SessionDocument } from '../types'

const REPO = 'https://github.com/victorsamueldaniel/RoundnetMatchmaking'
const ROWS = [
  { key: 'Name', value: 'Victor DANIEL' },
  { key: 'Role', value: 'Developer / Maintainer' },
  { key: 'Email', value: 'daniel.victor.samuel@gmail.com', href: 'mailto:daniel.victor.samuel@gmail.com', action: 'Email' },
  { key: 'GitHub', value: REPO, href: REPO, action: 'Open' },
]

/** Replace every player name by Player_N, in the roster and in the session. */
function anonymise(roster: { id: string }[], document: SessionDocument | null) {
  const alias = new Map<string, string>()
  const name = (id: string) => {
    if (!alias.has(id)) alias.set(id, `Player_${alias.size + 1}`)
    return alias.get(id)!
  }
  const players = roster.map((p) => ({ ...p, id: name(p.id), Name: name(p.id), Surname: '' }))
  const session = document && {
    ...document,
    players: document.players.map((p) => ({ ...p, id: name(p.id), Name: name(p.id), Surname: '' })),
    preferred_pairs: document.preferred_pairs.map((p) => ({ ...p, players: p.players.map(name) })),
    rounds: document.rounds.map((r) => ({
      ...r,
      games: r.games.map((g) => ({ team_a: g.team_a.map(name), team_b: g.team_b.map(name) })),
      bench: r.bench.map(name),
    })),
  }
  return { players, session, name, known: () => [...alias.keys()] }
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

export function ContactScreen() {
  const bugReport = () => {
    const s = useStore.getState()
    const { players, session, name, known } = anonymise(s.roster, s.document)
    // Longest names first so "Jean" does not replace the start of "Jeanne".
    const names = known().sort((a, b) => b.length - a.length)
    const consoleTail = names.length
      ? s.consoleText.slice(-20000).replace(new RegExp(names.map(escapeRegExp).join('|'), 'g'), (match) => name(match))
      : s.consoleText.slice(-20000)
    downloadJson(
      {
        created_at: new Date().toISOString(),
        user_agent: navigator.userAgent,
        screen: `${window.innerWidth}x${window.innerHeight}`,
        settings: s.settings,
        female_shift: s.femaleShift,
        extra_parameters: s.extraParameters,
        players_anonymized: players,
        session_anonymized: session,
        console_tail: consoleTail,
      },
      `bug_report_${Date.now()}.json`,
    )
    toast('success', 'Bug report downloaded. Player names are replaced by Player_N.')
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-brand-yellow">CONTACT</h2>
        <p className="mt-1 text-soft">This is a small open source project. Wanna contribute? Reach out!</p>
      </div>
      <Card>
        <dl className="divide-y divide-line">
          {ROWS.map((row) => (
            <div key={row.key} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
              <dt className="w-16 font-semibold">{row.key}</dt>
              <dd className="min-w-0 flex-1 truncate text-sm text-soft">{row.value}</dd>
              <dd className="flex gap-2">
                <Button
                  variant="ghost"
                  className="min-h-8 py-1"
                  onClick={() =>
                    navigator.clipboard.writeText(row.value).then(
                      () => toast('success', 'Copied.'),
                      () => toast('error', 'Copy failed.'),
                    )
                  }
                >
                  Copy
                </Button>
                {row.href && (
                  <a href={row.href} target="_blank" rel="noreferrer" className="inline-flex min-h-8 items-center rounded-lg border border-line px-3 text-sm text-soft hover:bg-raised">
                    {row.action}
                  </a>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </Card>
      <Card title="Found a bug?">
        <p className="mb-3 text-sm text-soft">
          Download a report with your settings, the current session and the console output, then attach it to a GitHub issue. Player
          names are replaced by Player_1, Player_2… before the file is created.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={bugReport}>
            Download bug report
          </Button>
          <a href={`${REPO}/issues/new`} target="_blank" rel="noreferrer" className="inline-flex min-h-10 items-center rounded-lg border border-line px-3.5 text-sm text-soft hover:bg-raised">
            Open a GitHub issue
          </a>
        </div>
      </Card>
    </div>
  )
}
