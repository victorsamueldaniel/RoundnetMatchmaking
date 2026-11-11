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
import { SPECTRUM } from './types'

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
export type HistoryOperation =
  | { kind: 'player_swaps'; swaps: PendingSwap[] }
  | { kind: 'round_reorder'; order: number[] }
export type GenerationAvailability = Record<string, boolean[]>
export type GenerationMatrixRows = string[]

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
  historyOperations: HistoryOperation[]
  historyCurrentIndex: number
  historyRewriteIndex: number | null
  recent: RecentSession[]
  pendingSwaps: PendingSwap[]
  pendingRoundOrder: number[] | null
  showLevels: boolean
  consoleText: string
  generationAvailability: GenerationAvailability
  generationMatrixRows: GenerationMatrixRows

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
  commitSession: (
    document: SessionDocument,
    view: SessionView,
    score: number,
    operation?: HistoryOperation,
  ) => void
  restoreVersion: (index: number, view: SessionView) => void
  setView: (view: SessionView) => void
  setPendingSwaps: (swaps: PendingSwap[]) => void
  setShowLevels: (value: boolean) => void
  appendConsole: (text: string) => void
  clearConsole: () => void
  setGenerationAvailability: (
    value: GenerationAvailability | ((prev: GenerationAvailability) => GenerationAvailability),
  ) => void
  setGenerationMatrixRows: (
    value: GenerationMatrixRows | ((prev: GenerationMatrixRows) => GenerationMatrixRows),
  ) => void
}

const DEFAULT_TYPES: RoundType[] = ['balanced', 'balanced', 'level', 'level']
const DEFAULT_GENDERS: RoundGender[] = ['open', 'mixed', 'mixed', 'open']
const MAX_CONSOLE = 400_000
const MAX_RECENT = 5

const normalizeSessionExtraParameters = (value: unknown, fallback: Record<string, unknown> | null) => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return fallback
  const extra = { ...(value as Record<string, unknown>) }
  delete extra.level_gap_tol
  delete extra.games_per_round
  delete extra.num_iter
  delete extra.lambda_weight
  delete extra.percentile
  delete extra.weight_same_teammate
  delete extra.never_met_bonus_per_player
  delete extra.never_met_bonus_cap
  delete extra.spectrum
  delete extra.female_shift
  delete extra.rounds_reordering
  delete extra.extra_parameters
  return extra
}

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

const capHistory = (history: HistoryEntry[]) => history

const stripEditorHistory = (document: SessionDocument): SessionDocument => {
  const { editor_and_games_history: _ignore, ...rest } = document as SessionDocument & {
    editor_and_games_history?: SessionDocument['editor_and_games_history']
  }
  return rest
}

const applySwapsToDocument = (
  document: SessionDocument,
  swaps: PendingSwap[],
): SessionDocument => {
  if (!swaps.length) return stripEditorHistory(document)
  const rounds = document.rounds.map((round) => ({
    ...round,
    games: round.games.map((game) => ({
      team_a: [...game.team_a],
      team_b: [...game.team_b],
    })),
    bench: [...round.bench],
    not_available: [...(round.not_available ?? [])],
  }))
  for (const swap of swaps) {
    const round = rounds[swap.round]
    if (!round) continue
    const lists = [...round.games.flatMap((game) => [game.team_a, game.team_b]), round.bench]
    const locate = (name: string) => {
      for (const list of lists) {
        const index = list.indexOf(name)
        if (index >= 0) return { list, index }
      }
      return null
    }
    const left = locate(swap.a)
    const right = locate(swap.b)
    if (left && right) {
      left.list[left.index] = swap.b
      right.list[right.index] = swap.a
    }
  }
  return { ...stripEditorHistory(document), rounds }
}

const applyRoundOrderToDocument = (
  document: SessionDocument,
  order: number[],
): SessionDocument => {
  if (!Array.isArray(order) || !order.length || order.length !== document.rounds.length) {
    return stripEditorHistory(document)
  }
  const normalized = order.map((value) => Number(value))
  if (
    normalized.some((value) => !Number.isInteger(value) || value < 0 || value >= document.rounds.length)
  ) {
    return stripEditorHistory(document)
  }
  if (new Set(normalized).size !== document.rounds.length) {
    return stripEditorHistory(document)
  }
  return { ...stripEditorHistory(document), rounds: normalized.map((idx) => document.rounds[idx]) }
}

const applyOperationToDocument = (
  document: SessionDocument,
  operation: HistoryOperation,
): SessionDocument => {
  if (operation.kind === 'round_reorder') return applyRoundOrderToDocument(document, operation.order)
  return applySwapsToDocument(document, operation.swaps)
}

const applyInverseOperationToDocument = (
  document: SessionDocument,
  operation: HistoryOperation,
): SessionDocument => {
  if (operation.kind === 'round_reorder') {
    // Stored order maps new index -> previous index. To step backward in history,
    // we need the inverse permutation (previous index -> new index).
    const order = operation.order ?? []
    const inverse = Array.from({ length: order.length }, () => -1)
    for (let nextIdx = 0; nextIdx < order.length; nextIdx += 1) {
      const previousIdx = Number(order[nextIdx])
      if (!Number.isInteger(previousIdx) || previousIdx < 0 || previousIdx >= order.length) {
        return stripEditorHistory(document)
      }
      inverse[previousIdx] = nextIdx
    }
    return applyRoundOrderToDocument(document, inverse)
  }
  return applySwapsToDocument(document, operation.swaps)
}

const withEditorHistory = (
  document: SessionDocument,
  history: HistoryEntry[],
  operations: HistoryOperation[],
  currentIndex: number,
): SessionDocument => ({
  ...stripEditorHistory(document),
  editor_and_games_history: {
    initial_score: Number(history[0]?.score ?? 0),
    applies: operations.map((operation, idx) => ({
      kind: operation.kind,
      score: Number(history[idx + 1]?.score ?? history[Math.min(idx + 1, history.length - 1)]?.score ?? 0),
      swaps: operation.kind === 'player_swaps'
        ? operation.swaps.map((swap) => ({
          round_idx: Number(swap.round),
          player1_id: String(swap.a),
          player2_id: String(swap.b),
        }))
        : undefined,
      order: operation.kind === 'round_reorder' ? operation.order.map((value) => Number(value)) : undefined,
    })),
    current_index: Math.max(0, Math.min(currentIndex, Math.max(0, operations.length))),
  },
})

const buildHistoryFromSource = (
  sourceDocument: SessionDocument,
  sourceIndex: number,
  operations: HistoryOperation[],
  initialScore: number,
  applyScores: number[],
): HistoryEntry[] => {
  const history: HistoryEntry[] = []
  const maxIndex = operations.length
  const start = Math.max(0, Math.min(sourceIndex, maxIndex))
  const source = stripEditorHistory(sourceDocument)
  for (let target = 0; target <= maxIndex; target += 1) {
    let doc = source
    if (target > start) {
      for (let idx = start; idx < target; idx += 1) {
        doc = applyOperationToDocument(doc, operations[idx] ?? { kind: 'player_swaps', swaps: [] })
      }
    } else if (target < start) {
      for (let idx = start - 1; idx >= target; idx -= 1) {
        doc = applyInverseOperationToDocument(doc, operations[idx] ?? { kind: 'player_swaps', swaps: [] })
      }
    }
    history.push({
      score: target === 0 ? initialScore : Number(applyScores[target - 1] ?? 0),
      document: doc,
    })
  }
  return history
}

const readEditorHistory = (
  document: SessionDocument,
): {
  history: HistoryEntry[]
  operations: HistoryOperation[]
  currentIndex: number
} | null => {
  const payload = document.editor_and_games_history as any
  if (!payload || typeof payload !== 'object') return null

  const appliesRaw = Array.isArray(payload.applies) ? payload.applies : []
  const operations: HistoryOperation[] = []
  const applyScores: number[] = []
  for (const apply of appliesRaw) {
    const score = Number(apply?.score)
    if (!Number.isFinite(score)) continue
    const hasOrder = Array.isArray(apply?.order)
    const kind = apply?.kind === 'round_reorder' || (!apply?.kind && hasOrder)
      ? 'round_reorder'
      : 'player_swaps'
    if (kind === 'round_reorder') {
      const rawOrder = Array.isArray(apply?.order) ? apply.order : []
      const order = rawOrder
        .map((value: unknown) => Number(value))
        .filter((value: number) => Number.isInteger(value))
      operations.push({ kind: 'round_reorder', order })
    } else {
      const rawSwaps = Array.isArray(apply?.swaps) ? apply.swaps : []
      const swaps: PendingSwap[] = []
      for (const rawSwap of rawSwaps) {
        const swapObj = rawSwap as any
        const round = Number(swapObj?.round_idx ?? swapObj?.round)
        const a = swapObj?.player1_id ?? swapObj?.a
        const b = swapObj?.player2_id ?? swapObj?.b
        if (!Number.isInteger(round) || round < 0 || typeof a !== 'string' || typeof b !== 'string') continue
        swaps.push({ round, a, b })
      }
      operations.push({ kind: 'player_swaps', swaps })
    }
    applyScores.push(score)
  }

  const initialScoreRaw = Number((payload as { initial_score?: unknown })?.initial_score)
  const initialScore = Number.isFinite(initialScoreRaw) ? initialScoreRaw : 0
  const rawIndex = Number(payload.current_index)
  const currentIndex = Number.isFinite(rawIndex) ? Math.trunc(rawIndex) : operations.length
  return {
    history: buildHistoryFromSource(document, currentIndex, operations, initialScore, applyScores),
    operations,
    currentIndex: Math.max(0, Math.min(currentIndex, operations.length)),
  }
}

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
      historyOperations: [],
      historyCurrentIndex: 0,
      historyRewriteIndex: null,
      recent: [],
      pendingSwaps: [],
      pendingRoundOrder: null,
      showLevels: false,
      consoleText: '',
      generationAvailability: {},
      generationMatrixRows: [],

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
          const nextAvailability: GenerationAvailability = {}
          for (const [playerId, row] of Object.entries(s.generationAvailability)) {
            if (!ids.has(playerId)) continue
            nextAvailability[playerId] = Array.isArray(row) ? row.map(Boolean) : []
          }
          const nextMatrixRows = s.generationMatrixRows.filter((playerId) => ids.has(playerId))
          return {
            roster: players,
            overrides: {},
            selected: s.selected.filter((id) => ids.has(id)),
            pairs: s.pairs.filter((pair) => pair.players.every((id) => ids.has(id))),
            generationAvailability: nextAvailability,
            generationMatrixRows: nextMatrixRows,
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
        set((s) => {
          const baseDocument = stripEditorHistory(document)
          const incoming = document.players ?? []
          const params = document.params ?? {}
          const shift = (params.female_shift as number) ?? 0

          // If the session had a female_shift applied at generation time, revert it
          // for display in the Session tab so levels aren't permanently mutated.
          const adjustedIncoming: Player[] = incoming.map((p) => {
            if (!shift) return p
            if (p.Gender === 'Female' && typeof p.Level === 'number' && p.Level !== null) {
              return { ...p, Level: (p.Level as number) - shift }
            }
            return p
          })

          const revertedCount = adjustedIncoming.reduce((acc, p, i) => {
            const orig = incoming[i]
            return acc + ((orig.Gender === 'Female' && typeof orig.Level === 'number' && orig.Level !== null && (orig.Level as number) !== (p.Level as number)) ? 1 : 0)
          }, 0)

          const selectedIds = adjustedIncoming.map((p) => p.id)
          const existingById = new Map(s.roster.map((p) => [p.id, p]))
          const mergedRoster = [...s.roster]
          const logs: string[] = []

          if (shift && revertedCount > 0) {
            logs.push(`Reverted female shift ${shift > 0 ? '-' : ''}${shift} on ${revertedCount} players`)
          }

          for (const p of adjustedIncoming) {
            const existing = existingById.get(p.id)
            if (!existing) {
              mergedRoster.push(p)
              logs.push(`Added player ${p.Name ?? p.id} (${p.id}) from session`)
            } else {
              const diffs: string[] = []
              const checkKeys: (keyof Player)[] = ['Name', 'Surname', 'Level', 'Gender'] as (keyof Player)[]
              for (const k of checkKeys) {
                const oldV = existing[k]
                const newV = p[k]
                if (oldV !== newV) diffs.push(`${k}: ${oldV ?? 'null'} → ${newV ?? 'null'}`)
              }
              for (const spec of SPECTRUM) {
                const oldV = (existing as any)[spec]
                const newV = (p as any)[spec]
                if (oldV !== newV) diffs.push(`${spec}: ${oldV ?? '0'} → ${newV ?? '0'}`)
              }
              if (diffs.length > 0) {
                // replace existing entry with incoming JSON player
                const idx = mergedRoster.findIndex((x) => x.id === p.id)
                if (idx >= 0) mergedRoster[idx] = p
                logs.push(`Applied JSON to ${p.Name ?? p.id} (${p.id}): ${diffs.join('; ')}`)
              }
            }
          }
          const roundCount = document.rounds?.length ?? 0
          const roundTypes = document.rounds?.map((r) => r.type_preference) ?? DEFAULT_TYPES.slice(0, roundCount)
          const roundGenders = document.rounds?.map((r) => r.gender_preference) ?? DEFAULT_GENDERS.slice(0, roundCount)
          const sameGames = document.rounds && document.rounds.length > 0 && document.rounds.every((r) => r.games.length === document.rounds[0].games.length)
          const savedGamesPerRound = params.games_per_round
          const gamesPerRound = typeof savedGamesPerRound === 'number'
            ? String(savedGamesPerRound)
            : typeof savedGamesPerRound === 'string'
              ? savedGamesPerRound
              : sameGames
                ? String(document.rounds[0].games.length)
                : 'auto'
          const settings = {
            numRounds: roundCount,
            gamesPerRound,
            levelGapTol: (params.level_gap_tol as number) ?? s.settings?.levelGapTol ?? 1,
            lambdaWeight: (params.lambda_weight as number) ?? s.settings?.lambdaWeight ?? 1,
            percentile: (params.percentile as number) ?? s.settings?.percentile ?? 10,
            spectrum: (params.spectrum as boolean) ?? s.settings?.spectrum ?? false,
            roundTypes,
            roundGenders,
          }
          const femaleShift = (params.female_shift as number) ?? s.femaleShift ?? 0
          const availabilityFromDocument = document.availability && typeof document.availability === 'object'
            ? document.availability
            : {}
          const generationAvailability: GenerationAvailability = Object.fromEntries(
            selectedIds.map((playerId) => {
              const row = availabilityFromDocument[playerId]
              const normalized = Array.isArray(row) ? row.slice(0, roundCount).map(Boolean) : []
              while (normalized.length < roundCount) normalized.push(true)
              return [playerId, normalized]
            }),
          )
          const nextConsole = logs.length
            ? s.consoleText + '\n' + new Date().toISOString() + ' - Session load:\n' + logs.join('\n') + '\n'
            : s.consoleText

          const loadedHistoryPayload = readEditorHistory(document)
          const history = loadedHistoryPayload
            ? loadedHistoryPayload.history
            : [{ score: view.summary.score, document: baseDocument }]
          const historyOperations = loadedHistoryPayload
            ? loadedHistoryPayload.operations
            : []
          const historyCurrentIndex = loadedHistoryPayload
            ? loadedHistoryPayload.currentIndex
            : history.length - 1
          const currentHistoryDocument = history[historyCurrentIndex]?.document ?? baseDocument
          const nextOperation = historyCurrentIndex < historyOperations.length
            ? historyOperations[historyCurrentIndex]
            : null
          const nextPendingSwaps =
            nextOperation && nextOperation.kind === 'player_swaps'
              ? nextOperation.swaps
              : []
          const nextPendingRoundOrder =
            nextOperation && nextOperation.kind === 'round_reorder'
              ? [...nextOperation.order]
              : null

          return {
            roster: mergedRoster,
            overrides: {},
            selected: selectedIds,
            pairs: document.preferred_pairs ?? [],
            saved: { selected: selectedIds, femaleShift, pairs: document.preferred_pairs ?? [] },
            settings,
            femaleShift,
            extraParameters: normalizeSessionExtraParameters(params.extra_parameters, s.extraDefaults ?? s.extraParameters),
            generationAvailability,
            document: withEditorHistory(currentHistoryDocument, history, historyOperations, historyCurrentIndex),
            view,
            history,
            historyOperations,
            historyCurrentIndex,
            historyRewriteIndex: null,
            pendingSwaps: nextPendingSwaps,
            pendingRoundOrder: nextPendingRoundOrder,
            recent: remember
              ? [{ savedAt: new Date().toISOString(), label, document: withEditorHistory(currentHistoryDocument, history, historyOperations, historyCurrentIndex) }, ...s.recent].slice(0, MAX_RECENT)
              : s.recent,
            consoleText: nextConsole.length > MAX_CONSOLE ? nextConsole.slice(-MAX_CONSOLE) : nextConsole,
          }
        }),
      clearRecent: () => set({ recent: [] }),
      commitSession: (document, view, score, operation) =>
        set((s) => {
          const rewriteIndex = typeof s.historyRewriteIndex === 'number'
            ? Math.max(0, Math.min(s.historyRewriteIndex, s.historyOperations.length))
            : null
          const currentIndex = rewriteIndex ?? Math.max(0, Math.min(s.historyCurrentIndex, s.historyOperations.length))
          const nextOperations = [...s.historyOperations]
          const nextApplyScores = nextOperations.map((_, idx) => Number(s.history[idx + 1]?.score ?? 0))
          const newOperation: HistoryOperation = operation
            ? operation
            : { kind: 'player_swaps', swaps: s.pendingSwaps.map((swap) => ({ ...swap })) }
          if (currentIndex < nextOperations.length) {
            nextOperations[currentIndex] = newOperation
            nextOperations.splice(currentIndex + 1)
            nextApplyScores[currentIndex] = Number(score)
            nextApplyScores.splice(currentIndex + 1)
          } else {
            nextOperations.push(newOperation)
            nextApplyScores.push(Number(score))
          }
          const nextIndex = Math.min(currentIndex + 1, nextOperations.length)
          const initialScore = Number(s.history[0]?.score ?? score)
          const currentDocument = stripEditorHistory(document)
          const nextHistory = capHistory(
            buildHistoryFromSource(currentDocument, nextIndex, nextOperations, initialScore, nextApplyScores),
          )
          const nextDocument = withEditorHistory(currentDocument, nextHistory, nextOperations, nextIndex)
          return {
            document: nextDocument,
            view,
            pendingSwaps: [],
            pendingRoundOrder: null,
            history: nextHistory,
            historyOperations: nextOperations,
            historyCurrentIndex: nextIndex,
            historyRewriteIndex: null,
            recent: s.recent.length
              ? [{ ...s.recent[0], document: nextDocument }, ...s.recent.slice(1)]
              : [{ savedAt: new Date().toISOString(), label: 'Edited session', document: nextDocument }],
          }
        }),
      restoreVersion: (index, view) =>
        set((s) => {
          if (index < 0 || index >= s.history.length) return {}
          const nextDocument = withEditorHistory(
            s.history[index].document,
            s.history,
            s.historyOperations,
            index,
          )
          const nextOperation = index < s.historyOperations.length ? s.historyOperations[index] : null
          const nextPending =
            nextOperation && nextOperation.kind === 'player_swaps'
              ? nextOperation.swaps
              : []
          const nextPendingRoundOrder =
            nextOperation && nextOperation.kind === 'round_reorder'
              ? [...nextOperation.order]
              : null
          return {
            document: nextDocument,
            view,
            pendingSwaps: nextPending,
            pendingRoundOrder: nextPendingRoundOrder,
            historyCurrentIndex: index,
            historyRewriteIndex: index,
            recent: s.recent.length
              ? [{ ...s.recent[0], document: nextDocument }, ...s.recent.slice(1)]
              : s.recent,
          }
        }),
      setView: (view) => set({ view }),
      setPendingSwaps: (swaps) => set({ pendingSwaps: swaps, pendingRoundOrder: null }),
      setShowLevels: (value) => set({ showLevels: value }),
      appendConsole: (text) =>
        set((s) => {
          const next = s.consoleText + text
          return { consoleText: next.length > MAX_CONSOLE ? next.slice(-MAX_CONSOLE) : next }
        }),
      clearConsole: () => set({ consoleText: '' }),
      setGenerationAvailability: (value) =>
        set((s) => ({
          generationAvailability: typeof value === 'function' ? value(s.generationAvailability) : value,
        })),
      setGenerationMatrixRows: (value) =>
        set((s) => ({
          generationMatrixRows: typeof value === 'function' ? value(s.generationMatrixRows) : value,
        })),
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
        historyOperations: s.historyOperations,
        historyCurrentIndex: s.historyCurrentIndex,
        pendingRoundOrder: s.pendingRoundOrder,
        recent: s.recent,
        generationAvailability: s.generationAvailability,
        generationMatrixRows: s.generationMatrixRows,
      }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.selected = state.saved.selected
          state.femaleShift = state.saved.femaleShift
          state.pairs = state.saved.pairs
          if (typeof state.historyCurrentIndex !== 'number') {
            state.historyCurrentIndex = Math.max(0, state.history.length - 1)
          }
          if (!Array.isArray((state as any).historyOperations)) {
            ;(state as any).historyOperations = []
          }
          if (!Array.isArray((state as any).pendingRoundOrder)) {
            ;(state as any).pendingRoundOrder = null
          }
          if (state.document) {
            state.document = withEditorHistory(
              stripEditorHistory(state.document),
              state.history,
              (state as any).historyOperations,
              state.historyCurrentIndex,
            )
          }
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
