import { lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import { fetchDefaults, viewSession } from './api'
import { toast, Toasts } from './components/toast'
import { Button } from './components/ui'
import { ContactScreen } from './screens/Contact'
import { EditorScreen } from './screens/Editor'
import { GamesScreen } from './screens/Games'
import { GenerateScreen } from './screens/Generate'
import { useStore, type Tab } from './store'

const PlotsScreen = lazy(() => import('./screens/Plots'))

const ICONS: Record<Tab, ReactNode> = {
  generate: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  editor: <path d="M7 4v16M17 4v16M3 8h8M13 16h8" />,
  games: <path d="M4 5h16v14H4zM4 10h16M12 10v9" />,
  plots: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  contact: <path d="M4 6h16v12H4zM4 7l8 6 8-6" />,
}

const TABS: { id: Tab; label: string; needsSession?: boolean }[] = [
  { id: 'generate', label: 'Session' },
  { id: 'editor', label: 'Editor', needsSession: true },
  { id: 'games', label: 'Games', needsSession: true },
  { id: 'plots', label: 'Plots', needsSession: true },
  { id: 'contact', label: 'Contact' },
]

function Icon({ tab }: { tab: Tab }) {
  return (
    <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {ICONS[tab]}
    </svg>
  )
}

export default function App() {
  const tab = useStore((s) => s.tab)
  const setTab = useStore((s) => s.setTab)
  const settings = useStore((s) => s.settings)
  const applyDefaults = useStore((s) => s.applyDefaults)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchDefaults()
      .then(applyDefaults)
      .catch((e: Error) => setError(e.message))
  }, [applyDefaults])

  const document = useStore((s) => s.document)
  const hasView = useStore((s) => s.view !== null)
  const setView = useStore((s) => s.setView)

  // The session document is kept in the browser; its view is recomputed after a reload.
  useEffect(() => {
    if (document && !hasView) viewSession(document).then(setView, (e: Error) => toast('error', e.message))
  }, [document, hasView, setView])

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [tab])

  const active = document === null && TABS.find((t) => t.id === tab)?.needsSession ? 'generate' : tab

  return (
    <div className="min-h-dvh pb-20 md:pb-0">
      <Toasts />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-4 py-2.5">
          <img src="/logo.png" alt="" className="size-9 rounded-full" />
          <h1 className="text-base font-bold tracking-wide sm:text-lg">
            ROUNDNET <span className="text-brand-yellow">MATCHMAKING</span>
          </h1>
          <nav className="ml-auto hidden gap-1 md:flex" aria-label="Sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                disabled={t.needsSession && document === null}
                onClick={() => setTab(t.id)}
                aria-current={active === t.id ? 'page' : undefined}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-35 ${
                  active === t.id ? 'bg-brand-yellow text-black' : 'text-soft hover:bg-raised'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-3 py-4 sm:px-4">
        {error ? (
          <div className="mx-auto max-w-md space-y-3 py-16 text-center">
            <p className="text-lg font-semibold">The server is not reachable.</p>
            <p className="text-sm text-muted">{error}</p>
            <Button variant="primary" onClick={() => location.reload()}>
              Retry
            </Button>
          </div>
        ) : !settings ? (
          <p className="py-16 text-center text-muted">Loading…</p>
        ) : (
          <>
            {active === 'generate' && <GenerateScreen />}
            {active === 'editor' && <EditorScreen />}
            {active === 'games' && <GamesScreen />}
            {active === 'plots' && (
              <Suspense fallback={<p className="py-16 text-center text-muted">Loading charts…</p>}>
                <PlotsScreen />
              </Suspense>
            )}
            {active === 'contact' && <ContactScreen />}
          </>
        )}
      </main>

      <nav className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-line bg-ink/95 backdrop-blur md:hidden" aria-label="Sections">
        <div className="grid grid-cols-5">
          {TABS.map((t) => (
            <button
              key={t.id}
              disabled={t.needsSession && document === null}
              onClick={() => setTab(t.id)}
              aria-current={active === t.id ? 'page' : undefined}
              className={`flex flex-col items-center gap-0.5 py-2 text-[11px] disabled:opacity-30 ${
                active === t.id ? 'text-brand-yellow' : 'text-muted'
              }`}
            >
              <Icon tab={t.id} />
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}
