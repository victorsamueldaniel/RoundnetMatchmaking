export type Gender = 'Male' | 'Female'

export const SPECTRUM = ['Prey', 'Equilibrist', 'Challenger', 'Chill', 'Hunter', 'Classist'] as const
export type Spectrum = (typeof SPECTRUM)[number]

export type Player = {
  id: string
  Name: string
  Surname: string
  Level: number | null
  Gender: Gender | null
} & Record<Spectrum, number>

export type RoundType = 'balanced' | 'level'
export type RoundGender = 'open' | 'mixed'

export type PreferredPair = { players: [string, string]; games: number }

export type RoundDoc = {
  type_preference: RoundType
  gender_preference: RoundGender
  games: { team_a: string[]; team_b: string[] }[]
  bench: string[]
}

export type SessionDocument = {
  version: number
  seed: number | null
  players: Player[]
  params: Record<string, unknown> & {
    games_per_round?: string | number | null
    lambda_weight?: number
    percentile?: number
    level_gap_tol?: number
    spectrum?: boolean
    female_shift?: number
  }
  preferred_pairs: PreferredPair[]
  rounds: RoundDoc[]
}

export type Breakdown = {
  terms: Record<string, number>
  new_people: number
  spectrum: { values: Record<Spectrum, number>; triggered: Record<Spectrum, boolean>; chosen: Spectrum | null } | null
  total: number
}

export type SlotView = {
  name: string
  level: number
  gender: string | null
  gain: number | null
  spec: Spectrum | null
  breakdown?: Breakdown | null
  pair_bonus?: number
}

export type RoundView = {
  type_preference: RoundType
  gender_preference: RoundGender
  games: { team_a: SlotView[]; team_b: SlotView[]; level_difference: number; gender_ok: boolean }[]
  bench: SlotView[]
}

export type Distribution = { values: number[] }

export type SessionView = {
  summary: {
    score: number
    mean: number
    std: number
    min: number
    max: number
    players: { name: string; level: number; gender: string | null; happiness: number; games_played: number }[]
    least_happy: string[]
    happiest: string[]
  }
  rounds: RoundView[]
  charts: {
    happiness: {
      stats: { mean: number; std: number; min: number; max: number }
      players: { name: string; level: number; happiness: number; games_played: number }[]
      by_gender: ({ gender: string } & Distribution)[]
      evolution: { name: string; values: number[] }[]
    }
    team: {
      nodes: { name: string; level: number; happiness: number; x: number; y: number }[]
      partner_edges: { a: string; b: string; count: number }[]
      opponent_edges: { a: string; b: string; count: number }[]
      levels_by_gender: ({ gender: string } & Distribution)[]
      max_partner_vs_opponent: { name: string; x: number; y: number; level: number }[]
    }
    spectrum: {
      attributes: Spectrum[]
      average: number[]
      happiness_by_dominant: ({ spectrum: string } & Distribution)[]
      chosen_counts: { spectrum: string; count: number }[]
      heatmap: { players: string[]; values: number[][] }
    } | null
  }
  repetitions: {
    teammates: { players: string[]; count: number; rounds: number[] }[]
    opponents: { players: string[]; count: number; rounds: number[] }[]
    never_met: string[]
  }
}

export type HistoryEntry = { score: number; document: SessionDocument }
