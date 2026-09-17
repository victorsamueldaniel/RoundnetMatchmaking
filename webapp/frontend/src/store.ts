import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Defaults } from './api'
import type {
  HistoryEntry,
  Player,
  PreferredPair,
  RoundGender,
  RoundType,
  SessionDocument,
  SessionView,
} from './types'

export type Tab = 'generate' | 'editor' | 'games' | 'plots' | 'contact'

/** Settings saved automatically as soon as they change (like the desktop app). */
export type Settings = {
  numRounds: number
  gamesPerRound: string
  levelGapTol: number
  lambdaWeight: number
  percentile: number
  spectrum: boolean
  roundTypes: RoundType[]
  roundGenders: RoundGender[]
}

/** Settings only saved when the user confirms (selection, female shift, pairs). */
export type Confirmable = {
  selected: string[]
  femaleShift: number
  pairs: PreferredPair[]
}

export type PendingSwap = { round: number; a: string; b: string }

export type RecentSession = { savedAt: string; label: string; document: SessionDocument }

type State = Confirmable & {
  tab: Tab
  roster: Player[]
  overrides: Record<string, Partial<Player>>
  settings: Settings | null
  saved: Confirmable
  extraParameters: Record<string, unknown> | null
  extraDefaults: Record<string, unknown> | null
  document: SessionDocument | null
  view: SessionView | null
  history: HistoryEntry[]
  recent: RecentSession[]
  pendingSwaps: PendingSwap[]
  showLevels: boolean
  consoleText: string

  setTab: (tab: Tab) => void
  applyDefaults: (defaults: Defaults) => void
  setRoster: (players: Player[]) => void
  upsertPlayer: (player: Player) => void
  setOverride: (id: string, values: Partial<Player> | null) => void
  updateSettings: (patch: Partial<Settings>) => void
  setRounds: (count: number) => void
  toggleSelected: (id: string) => void
  setSelected: (ids: string[]) => void
  setFemaleShift: (value: number) => void
  setPairs: (pairs: PreferredPair[]) => void
  saveConfirmable: (keys: (keyof Confirmable)[]) => void
  discardConfirmable: (keys: (keyof Confirmable)[]) => void
  setExtraParameters: (value: Record<string, unknown>) => void
  openSession: (document: SessionDocument, view: SessionView, label: string, remember?: boolean) => void
  clearRecent: () => void
  commitSession: (document: SessionDocument, view: SessionView, score: number) => void
  restoreVersion: (index: number, view: SessionView) => void
  setView: (view: SessionView) => void
  setPendingSwaps: (swaps: PendingSwap[]) => void
  setShowLevels: (value: boolean) => void
  appendConsole: (text: string) => void
  clearConsole: () => void
}

const DEFAULT_TYPES: RoundType[] = ['balanced', 'balanced', 'level', 'level']
const DEFAULT_GENDERS: RoundGender[] = ['open', 'mixed', 'mixed', 'open']
const MAX_CONSOLE = 400_000
const MAX_HISTORY = 30
const MAX_RECENT = 5

/** localStorage that never throws: a full or blocked storage must not break the app. */
let storageWarned = false
const safeStorage = {
  getItem: (name: string) => {
    try {
      return localStorage.getItem(name)
    } catch {
      return null
    }
  },
  setItem: (name: string, value: string) => {
    try {
      localStorage.setItem(name, value)
    } catch {
      if (!storageWarned) {
        storageWarned = true
        console.warn('Browser storage is full: recent changes are not saved. Clear old sessions to fix it.')
      }
    }
  },
  removeItem: (name: string) => {
    try {
      localStorage.removeItem(name)
    } catch {
      // nothing to remove
    }
  },
}

/** Keep the initial version and the latest ones. */
const capHistory = (history: HistoryEntry[]) =>
  history.length > MAX_HISTORY ? [history[0], ...history.slice(history.length - MAX_HISTORY + 1)] : history

export const useStore = create<State>()(
  persist(
    (set) => ({
      tab: 'generate',
      roster: [],
      overrides: {},
      settings: null,
      selected: [],
      femaleShift: 0,
      pairs: [],
      saved: { selected: [], femaleShift: 0, pairs: [] },
      extraParameters: null,
      extraDefaults: null,
      document: null,
      view: null,
      history: [],
      recent: [],
      pendingSwaps: [],
      showLevels: false,
      consoleText: '',

      setTab: (tab) => set({ tab }),
      applyDefaults: (defaults) =>
        set((s) => ({
          extraDefaults: defaults.extra_parameters,
          extraParameters: s.extraParameters ?? defaults.extra_parameters,
          settings: s.settings ?? {
            numRounds: defaults.ui.num_rounds,
            gamesPerRound: defaults.ui.games_per_round,
            levelGapTol: defaults.ui.level_gap_tol,
            lambdaWeight: defaults.ui.lambda_weight,
            percentile: defaults.ui.percentile,
            spectrum: defaults.ui.spectrum_enabled,
            roundTypes: defaults.ui.round_type_preferences,
            roundGenders: defaults.ui.round_gender_preferences,
          },
        })),
      setRoster: (players) =>
        set((s) => {
          const ids = new Set(players.map((p) => p.id))
          return {
            roster: players,
            overrides: {},
            selected: s.selected.filter((id) => ids.has(id)),
            pairs: s.pairs.filter((pair) => pair.players.every((id) => ids.has(id))),
          }
        }),
      upsertPlayer: (player) =>
        set((s) => {
          const exists = s.roster.some((p) => p.id === player.id)
          return {
            roster: exists ? s.roster.map((p) => (p.id === player.id ? player : p)) : [...s.roster, player],
            selected: exists || s.selected.includes(player.id) ? s.selected : [...s.selected, player.id],
          }
        }),
      setOverride: (id, values) =>
        set((s) => {
          const overrides = { ...s.overrides }
          if (values) overrides[id] = values
          else delete overrides[id]
          return { overrides }
        }),
      updateSettings: (patch) => set((s) => ({ settings: s.settings && { ...s.settings, ...patch } })),
      setRounds: (count) =>
        set((s) => {
          if (!s.settings) return {}
          const clamp = Math.max(1, Math.min(10, count))
          const pick = <T,>(list: T[], defaults: T[]) =>
            Array.from({ length: clamp }, (_, i) => list[i] ?? defaults[i % defaults.length])
          return {
            settings: {
              ...s.settings,
              numRounds: clamp,
              roundTypes: pick(s.settings.roundTypes, DEFAULT_TYPES),
              roundGenders: pick(s.settings.roundGenders, DEFAULT_GENDERS),
            },
          }
        }),
      toggleSelected: (id) =>
        set((s) => ({
          selected: s.selected.includes(id) ? s.selected.filter((x) => x !== id) : [...s.selected, id],
        })),
      setSelected: (ids) => set({ selected: ids }),
      setFemaleShift: (value) => set({ femaleShift: value }),
      setPairs: (pairs) => set({ pairs }),
      saveConfirmable: (keys) =>
        set((s) => ({ saved: { ...s.saved, ...Object.fromEntries(keys.map((k) => [k, s[k]])) } })),
      discardConfirmable: (keys) => set((s) => Object.fromEntries(keys.map((k) => [k, s.saved[k]]))),
      setExtraParameters: (value) => set({ extraParameters: value }),
      openSession: (document, view, label, remember = true) =>
        set((s) => ({
          document,
          view,
          history: [{ score: view.summary.score, document }],
          pendingSwaps: [],
          recent: remember ? [{ savedAt: new Date().toISOString(), label, document }, ...s.recent].slice(0, MAX_RECENT) : s.recent,
        })),
      clearRecent: () => set({ recent: [] }),
      commitSession: (document, view, score) =>
        set((s) => ({
          document,
          view,
          pendingSwaps: [],
          history: capHistory([...s.history, { score, document }]),
          recent: s.recent.length
            ? [{ ...s.recent[0], document }, ...s.recent.slice(1)]
            : [{ savedAt: new Date().toISOString(), label: 'Edited session', document }],
        })),
      restoreVersion: (index, view) =>
        set((s) => ({
          document: s.history[index].document,
          view,
          pendingSwaps: [],
          history: s.history.slice(0, index + 1),
        })),
      setView: (view) => set({ view }),
      setPendingSwaps: (swaps) => set({ pendingSwaps: swaps }),
      setShowLevels: (value) => set({ showLevels: value }),
      appendConsole: (text) =>
        set((s) => {
          const next = s.consoleText + text
          return { consoleText: next.length > MAX_CONSOLE ? next.slice(-MAX_CONSOLE) : next }
        }),
      clearConsole: () => set({ consoleText: '' }),
    }),
    {
      name: 'roundnet-matchmaking',
      version: 1,
      storage: createJSONStorage(() => safeStorage),
      partialize: (s) => ({
        roster: s.roster,
        overrides: s.overrides,
        settings: s.settings,
        saved: s.saved,
        extraParameters: s.extraParameters,
        document: s.document,
        history: s.history,
        recent: s.recent,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.selected = state.saved.selected
          state.femaleShift = state.saved.femaleShift
          state.pairs = state.saved.pairs
        }
      },
    },
  ),
)

/** Roster with the per-player edits applied. */
export function effectivePlayers(roster: Player[], overrides: Record<string, Partial<Player>>): Player[] {
  return roster.map((p) => (overrides[p.id] ? { ...p, ...overrides[p.id] } : p))
}

export const unsavedKeys = (s: Confirmable & { saved: Confirmable }) =>
  (['selected', 'femaleShift', 'pairs'] as const).filter(
    (k) => JSON.stringify(s[k]) !== JSON.stringify(s.saved[k]),
  )

export const CONFIRMABLE_LABELS: Record<keyof Confirmable, string> = {
  selected: 'Selected players',
  femaleShift: 'Female level shift',
  pairs: 'Preferred pairs',
}
