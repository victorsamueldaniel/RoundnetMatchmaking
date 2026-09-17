import type { Player, PreferredPair, RoundGender, RoundType, SessionDocument, SessionView } from './types'

export type Defaults = {
  ui: {
    num_rounds: number
    games_per_round: string
    level_gap_tol: number
    lambda_weight: number
    percentile: number
    spectrum_enabled: boolean
    round_type_preferences: RoundType[]
    round_gender_preferences: RoundGender[]
  }
  extra_parameters: Record<string, unknown>
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch {
      // keep the status line
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

function post(path: string, body: unknown) {
  return fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
}

export const fetchDefaults = () => fetch('/api/defaults').then((r) => json<Defaults>(r))

export async function parsePlayers(file: File) {
  const form = new FormData()
  form.append('file', file)
  const response = await fetch('/api/players/parse', { method: 'POST', body: form })
  return json<{ errors: string[]; players?: Player[] }>(response)
}

export async function exportPlayers(players: Player[]) {
  const response = await post('/api/players/export', players)
  if (!response.ok) throw new Error(`Export failed (${response.status})`)
  return response.blob()
}

export type GenerateRequest = {
  players: Player[]
  amount_of_rounds: number
  type_preferences: RoundType[]
  gender_preferences: RoundGender[]
  games_per_round: number | null
  level_gap_tol: number
  lambda_weight: number
  percentile: number
  female_shift: number
  spectrum: boolean
  preferred_pairs: PreferredPair[]
  extra_parameters: Record<string, unknown>
}

export type GenerateEvent =
  | { type: 'log'; text: string }
  | { type: 'progress'; seed: number; first: number; last: number }
  | { type: 'result'; document: SessionDocument; view: SessionView }
  | { type: 'error'; message: string }

/** Streams newline-delimited JSON events while the server generates a session. */
export async function generateSession(request: GenerateRequest, onEvent: (event: GenerateEvent) => void) {
  const response = await post('/api/sessions/generate', request)
  if (!response.ok || !response.body) {
    await json(response)
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    let newline = buffer.indexOf('\n')
    while (newline >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) onEvent(JSON.parse(line) as GenerateEvent)
      newline = buffer.indexOf('\n')
    }
    if (done) return
  }
}

export const viewSession = (document: SessionDocument) =>
  post('/api/sessions/view', { document }).then((r) => json<SessionView>(r))

export const sessionReport = (document: SessionDocument) =>
  post('/api/sessions/report', { document }).then((r) => json<{ text: string }>(r))

export async function sessionXlsx(document: SessionDocument, readOnly: boolean) {
  const response = await post(`/api/sessions/xlsx?read_only=${readOnly}`, { document })
  if (!response.ok) throw new Error(`Excel export failed (${response.status})`)
  return response.blob()
}

export async function sessionPng(document: SessionDocument, showLevels: boolean) {
  const response = await post('/api/sessions/png', { document, show_levels: showLevels })
  if (!response.ok) throw new Error(`Image export failed (${response.status})`)
  return response.blob()
}
