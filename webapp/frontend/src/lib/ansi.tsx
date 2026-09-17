import type { ReactNode } from 'react'

const COLORS: Record<string, string> = {
  '91': '#f87171',
  '92': '#4ade80',
  '93': '#facc15',
  '94': '#60a5fa',
  '95': '#e879f9',
  '96': '#22d3ee',
}

/** Render the engine's ANSI-colored console text as colored spans. */
export function renderAnsi(text: string): ReactNode[] {
  const out: ReactNode[] = []
  const pattern = /\x1b\[([\d;]*)m/g
  let color: string | undefined
  let bold = false
  let last = 0
  let key = 0
  const push = (chunk: string) => {
    if (chunk) out.push(<span key={key++} style={{ color, fontWeight: bold ? 700 : undefined }}>{chunk}</span>)
  }
  for (let match = pattern.exec(text); match; match = pattern.exec(text)) {
    push(text.slice(last, match.index))
    for (const code of match[1].split(';')) {
      if (code === '' || code === '0') {
        color = undefined
        bold = false
      } else if (code === '1') bold = true
      else if (COLORS[code]) color = COLORS[code]
    }
    last = pattern.lastIndex
  }
  push(text.slice(last))
  return out
}
