/** Accent-insensitive, case-insensitive sort key (same rule as the desktop player grid). */
export const sortKey = (value: string) =>
  value.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

export const byName = <T,>(get: (item: T) => string) => (a: T, b: T) =>
  sortKey(get(a)).localeCompare(sortKey(get(b)))

export const signed = (value: number, digits = 1) => `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`

export const ROUND_ABBREV: Record<string, string> = { balanced: 'bal', level: 'lvl', mixed: 'mix', open: 'opn' }

export const SPEC_ABBREV: Record<string, string> = {
  Prey: 'Prey',
  Hunter: 'Hntr',
  Challenger: 'Clgr',
  Classist: 'Clst',
  Equilibrist: 'Equl',
  Chill: 'Chll',
}

export const SPEC_HELP: Record<string, string> = {
  Prey: 'Enjoys losing and facing much stronger opponents, finds value in difficult, one-sided challenges.',
  Equilibrist: 'Prefers balanced games where both teams are evenly matched in skill.',
  Challenger: 'Likes playing against opponents slightly above their own level to grow and improve.',
  Chill: 'Just here for fun, prefers relaxed games with no pressure or intensity.',
  Hunter: 'Enjoys dominating weaker opponents and winning convincingly.',
  Classist: 'Prefers playing with others of exactly the same skill level.',
}

/** Games Editor preview color: white under 0.05, then towards green or red, saturating at 5. */
export function deltaColor(delta: number) {
  if (Math.abs(delta) < 0.05) return null
  const t = Math.min(Math.abs(delta) / 5, 1)
  const target = delta > 0 ? [0, 204, 68] : [255, 51, 34]
  const channel = (hi: number) => Math.round(255 + (hi - 255) * t)
  return `rgb(${channel(target[0])}, ${channel(target[1])}, ${channel(target[2])})`
}

export function quantile(sorted: number[], q: number) {
  if (!sorted.length) return NaN
  const pos = (sorted.length - 1) * q
  const lo = Math.floor(pos)
  const hi = Math.ceil(pos)
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo)
}

export function median(values: number[]) {
  return quantile([...values].sort((a, b) => a - b), 0.5)
}
