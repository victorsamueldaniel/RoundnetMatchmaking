import Plotly from 'plotly.js-dist-min'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Card, Segmented } from '../components/ui'
import { useStore } from '../store'
import type { SessionView } from '../types'

// Chart tokens for the dark panel surface (#2e2e2e); categorical slots validated against it.
const INK = '#ffffff'
const INK_2 = '#c3c2b7'
const MUTED = '#898781'
const GRID = '#3d3d3b'
const AXIS = '#4a4a47'
const SURFACE = '#2e2e2e'
const SERIES = ['#3987e5', '#d95926', '#199e70']
const HIGHLIGHT = '#fed403'
// One-hue sequential ramp: low values sit near the surface, high values are light.
const SEQUENTIAL: [number, string][] = [
  [0, '#fed403'],
  // [0.5, '#b1b1b1'],
  [1, '#7F0401'],
]

const axis = (title: string, extra: Partial<Plotly.LayoutAxis> = {}): Partial<Plotly.LayoutAxis> => ({
  title: { text: title, font: { color: INK_2, size: 12 } },
  gridcolor: GRID,
  linecolor: AXIS,
  zerolinecolor: AXIS,
  tickfont: { color: MUTED, size: 11 },
  ...extra,
})

const baseLayout = (extra: Partial<Plotly.Layout> = {}): Partial<Plotly.Layout> => ({
  paper_bgcolor: SURFACE,
  plot_bgcolor: SURFACE,
  font: { family: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: INK, size: 12 },
  margin: { l: 52, r: 16, t: 12, b: 48 },
  hoverlabel: { bgcolor: '#1a1a19', bordercolor: AXIS, font: { color: INK } },
  showlegend: false,
  dragmode: false,
  ...extra,
})

function Chart({ data, layout, height = 340 }: { data: Plotly.Data[]; layout: Partial<Plotly.Layout>; height?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    Plotly.react(el, data, { ...layout, height, autosize: true }, { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['select2d', 'lasso2d'] })
  }, [data, layout, height])
  useEffect(() => {
    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])
  return <div ref={ref} className="w-full" style={{ height }} />
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <Card title={title}>
      {subtitle && <p className="-mt-1 mb-2 text-xs text-muted">{subtitle}</p>}
      {children}
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-panel px-3 py-2">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-lg font-semibold">{value.toFixed(2)}</div>
    </div>
  )
}

function HappinessTab({ charts }: { charts: SessionView['charts'] }) {
  const h = charts.happiness
  const [highlight, setHighlight] = useState('')
  const happiness = h.players.map((p) => p.happiness)
  const bins = new Set(happiness).size

  const evolution = useMemo<Plotly.Data[]>(() => {
    const lines = h.evolution.map((p) => ({
      type: 'scatter' as const,
      mode: 'lines' as const,
      name: p.name,
      x: p.values.map((_, i) => i),
      y: p.values,
      line: { width: p.name === highlight ? 3 : 1.5, color: p.name === highlight ? HIGHLIGHT : 'rgba(163,163,163,0.45)', shape: 'linear' as const },
      hovertemplate: `<b>%{y}</b> ${p.name}<br>after round %{x}<extra></extra>`,
    }))
    return [...lines.filter((l) => l.name !== highlight), ...lines.filter((l) => l.name === highlight)]
  }, [h.evolution, highlight])

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Mean" value={h.stats.mean} />
        <Stat label="Std" value={h.stats.std} />
        <Stat label="Min" value={h.stats.min} />
        <Stat label="Max" value={h.stats.max} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Happiness distribution" subtitle="Number of players per happiness score">
          <Chart
            data={[{ type: 'histogram', x: happiness, nbinsx: Math.max(1, bins), marker: { color: SERIES[0], line: { color: SURFACE, width: 2 } }, hovertemplate: '<b>%{y}</b> players<br>happiness %{x}<extra></extra>' }]}
            layout={baseLayout({ xaxis: axis('Happiness score'), yaxis: axis('Number of players'), bargap: 0.08 })}
          />
        </Panel>
        <LevelVsHappinessChart h={h} />
        <Panel title="Happiness by gender" subtitle="Box = quartiles, dashed line = mean">
          <Chart
            data={h.by_gender.map((g, i) => ({
              type: 'box',
              name: `${g.gender} (n=${g.values.length})`,
              y: g.values,
              boxmean: true,
              marker: { color: SERIES[i % SERIES.length] },
              line: { width: 2 },
              fillcolor: `${SERIES[i % SERIES.length]}33`,
            }))}
            layout={baseLayout({ yaxis: axis('Happiness score'), xaxis: axis('') })}
          />
        </Panel>
        <Panel title="Happiness evolution by round" subtitle="Cumulative happiness per player">
          <label className="mb-2 flex items-center gap-2 text-sm">
            <span className="text-muted">Highlight</span>
            <select value={highlight} onChange={(e) => setHighlight(e.target.value)} className="min-h-9 rounded-lg border border-line bg-ink px-2">
              <option value="">No player</option>
              {h.evolution.map((p) => (
                <option key={p.name}>{p.name}</option>
              ))}
            </select>
          </label>
          <Chart data={evolution} layout={baseLayout({ xaxis: axis('Round number', { dtick: 1 }), yaxis: axis('Cumulative happiness'), hovermode: 'closest' })} />
        </Panel>
      </div>
    </div>
  )
}

function network(nodes: SessionView['charts']['team']['nodes'], edges: { a: string; b: string; count: number }[]): Plotly.Data[] {
  const at = new Map(nodes.map((n) => [n.name, n]))
  const widths = [...new Set(edges.map((e) => e.count))]
  const edgeTraces: Plotly.Data[] = widths.map((count) => {
    const x: (number | null)[] = []
    const y: (number | null)[] = []
    for (const e of edges.filter((edge) => edge.count === count)) {
      x.push(at.get(e.a)!.x, at.get(e.b)!.x, null)
      y.push(at.get(e.a)!.y, at.get(e.b)!.y, null)
    }
    const edgeColor = count < 2 ? 'rgba(195, 183, 183, 0.25)' : 'rgb(218, 215, 195)'
    return { type: 'scatter', mode: 'lines', x, y, hoverinfo: 'skip', line: { width: 1.5 * (count ** (3 / 2)), color: edgeColor } }
  })
  const maxHappiness = Math.max(...nodes.map((n) => n.happiness), 1)
  return [
    ...edgeTraces,
    {
      type: 'scatter',
      mode: 'text+markers',
      x: nodes.map((n) => n.x),
      y: nodes.map((n) => n.y),
      text: nodes.map((n) => n.name),
      textposition: 'top center',
      textfont: { color: INK_2, size: 10 },
      marker: {
        size: nodes.map((n) => 10 + (Math.max(n.happiness, 0) / maxHappiness) * 18),
        color: nodes.map((n) => n.level),
        colorscale: SEQUENTIAL,
        showscale: true,
        colorbar: { title: { text: 'Level', font: { color: INK_2 } }, tickfont: { color: MUTED }, thickness: 10, outlinewidth: 0 },
        line: { color: SURFACE, width: 2 },
      },
      customdata: nodes.map((n) => [n.level, n.happiness]),
      hovertemplate: '<b>%{text}</b><br>level %{customdata[0]}<br>happiness %{customdata[1]}<extra></extra>',
    },
  ]
}

const hidden = { visible: false }

function TeamTab({ view }: { view: SessionView }) {
  const t = view.charts.team
  const rep = view.repetitions
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <PartnershipNetworkPanel t={t} />
        <Panel title="Opponent network" subtitle="Edge = faced at least twice, thickness = times faced">
          <Chart data={network(t.nodes, t.opponent_edges)} layout={baseLayout({ xaxis: hidden, yaxis: hidden, margin: { l: 8, r: 8, t: 8, b: 8 } })} height={400} />
        </Panel>
        <Panel title="Level distribution by gender">
          <Chart
            data={t.levels_by_gender.map((g, i) => ({
              type: 'violin',
              name: `${g.gender} (n=${g.values.length})`,
              y: g.values,
              box: { visible: true },
              meanline: { visible: true },
              points: 'all',
              line: { color: SERIES[i % SERIES.length], width: 2 },
              fillcolor: `${SERIES[i % SERIES.length]}33`,
              marker: { color: SERIES[i % SERIES.length], size: 5 },
            }))}
            layout={baseLayout({ yaxis: axis('Player level'), xaxis: axis('') })}
          />
        </Panel>
        <MaxPartnerPanel t={t} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {(
          [
            ['Played together twice or more', rep.teammates],
            ['Faced each other twice or more', rep.opponents],
          ] as const
        ).map(([title, rows]) => (
          <Card key={title} title={title}>
            {rows.length ? (
              <table className="w-full text-sm">
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.players.join('|')} className="border-t border-line first:border-0">
                      <td className="py-1">{r.players.join(' & ')}</td>
                      <td className="py-1 text-right tabular-nums">{r.count}×</td>
                      <td className="py-1 pl-2 text-right text-muted">R{r.rounds.join(', R')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-muted">None</p>
            )}
          </Card>
        ))}
        <Card title="Never met">
          {rep.never_met.length ? (
            <ul className="scroll-thin max-h-72 space-y-1 overflow-y-auto text-sm">
              {rep.never_met.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">Everybody met everybody.</p>
          )}
        </Card>
      </div>
    </div>
  )
}

function SpectrumTab({ charts }: { charts: SessionView['charts'] }) {
  const s = charts.spectrum
  if (!s) return <Card>No spectrum data available for analysis.</Card>
  const total = s.chosen_counts.reduce((a, c) => a + c.count, 0)
  const chosen = [...s.chosen_counts].sort((a, b) => a.count - b.count)
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Panel title="Average spectrum profile">
        <Chart
          data={[
            {
              type: 'scatterpolar',
              r: [...s.average, s.average[0]],
              theta: [...s.attributes, s.attributes[0]],
              fill: 'toself',
              fillcolor: `${SERIES[0]}1a`,
              line: { color: SERIES[0], width: 2 },
              marker: { size: 8, color: SERIES[0] },
              hovertemplate: '<b>%{r:.2f}</b> %{theta}<extra></extra>',
            },
          ]}
          layout={baseLayout({
            polar: {
              bgcolor: SURFACE,
              radialaxis: { gridcolor: GRID, linecolor: AXIS, tickfont: { color: MUTED } },
              angularaxis: { gridcolor: GRID, linecolor: AXIS, tickfont: { color: INK_2 } },
            },
            margin: { l: 40, r: 40, t: 24, b: 24 },
          })}
        />
      </Panel>
      <Panel title="Happiness by dominant spectrum">
        <Chart
          data={s.happiness_by_dominant.map((g) => ({
            type: 'box',
            name: `${g.spectrum} (n=${g.values.length})`,
            y: g.values,
            marker: { color: SERIES[0] },
            line: { width: 2 },
            fillcolor: `${SERIES[0]}33`,
          }))}
          layout={baseLayout({ yaxis: axis('Happiness score'), xaxis: axis('') })}
        />
      </Panel>
      <Panel title="Spectrum types chosen during games" subtitle="Share of all games played">
        <Chart
          data={[
            {
              type: 'bar',
              orientation: 'h',
              y: chosen.map((c) => c.spectrum),
              x: chosen.map((c) => c.count),
              text: chosen.map((c) => `${((c.count / (total || 1)) * 100).toFixed(1)}%`),
              textposition: 'outside',
              textfont: { color: INK_2 },
              cliponaxis: false,
              marker: { color: SERIES[0] },
              width: 0.6,
              hovertemplate: '<b>%{x}</b> games<br>%{y}<extra></extra>',
            },
          ]}
          layout={baseLayout({ xaxis: axis('Games'), yaxis: axis(''), margin: { l: 90, r: 56, t: 12, b: 48 } })}
        />
      </Panel>
      <PlayerSpectrumChart s={s} />
    </div>
  )
}

export default function PlotsScreen() {
  const view = useStore((s) => s.view)
  const [tab, setTab] = useState<'main' | 'happiness' | 'spectrum' | 'team'>('main')
  if (!view) return <p className="py-16 text-center text-muted">Loading session…</p>
  return (
    <div className="space-y-4">
      <div className="scroll-thin overflow-x-auto">
        <Segmented
          label="Charts"
          value={tab}
          options={[
            { value: 'main', label: 'Main charts' },
            { value: 'happiness', label: 'Happiness overview' },
            { value: 'spectrum', label: 'Spectrum analysis' },
            { value: 'team', label: 'Team analysis' },
          ]}
          onChange={setTab}
        />
      </div>
      {tab === 'main' && <MainTab view={view} />}
      {tab === 'happiness' && <HappinessTab charts={view.charts} />}
      {tab === 'spectrum' && <SpectrumTab charts={view.charts} />}
      {tab === 'team' && <TeamTab view={view} />}
    </div>
  )
}

function MainTab({ view }: { view: SessionView }) {
  const h = view.charts.happiness
  const s = view.charts.spectrum
  const t = view.charts.team

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <LevelVsHappinessChart h={h} />
        <PlayerSpectrumChart s={s} />
        <PartnershipNetworkPanel t={t} />
        <MaxPartnerPanel t={t} />
      </div>
    </div>
  )
}

function LevelVsHappinessChart({ h }: { h: SessionView['charts']['happiness'] }) {
  return (
    <Panel title="Level vs happiness" subtitle="Dot size = games played, color = happiness">
      <Chart
        data={[
          {
            type: 'scatter',
            mode: 'text+markers',
            x: h.players.map((p) => p.level),
            y: h.players.map((p) => p.happiness),
            text: h.players.map((p) => p.name),
            textposition: 'top right',
            textfont: { color: INK_2, size: 10 },
            marker: {
              size: h.players.map((p) => 1 + p.games_played * 6),
              color: h.players.map((p) => p.happiness),
              colorscale: SEQUENTIAL,
              line: { color: SURFACE, width: 2 },
            },
            customdata: h.players.map((p) => p.games_played),
            hovertemplate: '<b>%{text}</b><br>level %{x}, happiness %{y}<br>%{customdata} games<extra></extra>',
          },
        ]}
        layout={baseLayout({ xaxis: axis('Player level'), yaxis: axis('Happiness score') })}
      />
    </Panel>
  )
}

function PlayerSpectrumChart({ s }: { s?: SessionView['charts']['spectrum'] }) {
  if (!s) return (
    <Panel title="Player spectrum profiles">
      <p className="text-sm text-muted">No spectrum data available for analysis.</p>
    </Panel>
  )
  return (
    <Panel title="Player spectrum profiles">
      <Chart
        height={Math.max(340, s.heatmap.players.length * 22 + 80)}
        data={[
          {
            type: 'heatmap',
            z: s.heatmap.values,
            x: s.attributes,
            y: s.heatmap.players,
            colorscale: SEQUENTIAL,
            xgap: 2,
            ygap: 2,
            texttemplate: '%{z}',
            textfont: { size: 11 },
            colorbar: { thickness: 10, outlinewidth: 0, tickfont: { color: MUTED } },
            hovertemplate: '<b>%{z}</b> %{x}<br>%{y}<extra></extra>',
          },
        ]}
        layout={baseLayout({ xaxis: axis('', { side: 'top' }), yaxis: axis('', { autorange: 'reversed' }), margin: { l: 90, r: 16, t: 40, b: 12 } })}
      />
    </Panel>
  )
}

function PartnershipNetworkPanel({ t }: { t: SessionView['charts']['team'] }) {
  return (
    <Panel title="Partnership network" subtitle="Node size = happiness, color = level, edge thickness = times as teammates">
      <Chart data={network(t.nodes, t.partner_edges)} layout={baseLayout({ xaxis: hidden, yaxis: hidden, margin: { l: 8, r: 8, t: 8, b: 8 } })} height={400} />
    </Panel>
  )
}

function MaxPartnerPanel({ t }: { t: SessionView['charts']['team'] }) {
  return (
    <Panel title="Max partner vs max opponent level" subtitle="Color = player level">
      <Chart
        data={[
          {
            type: 'scatter',
            mode: 'text+markers',
            x: t.max_partner_vs_opponent.map((p) => p.x),
            y: t.max_partner_vs_opponent.map((p) => p.y),
            text: t.max_partner_vs_opponent.map((p) => p.name),
            textposition: 'top right',
            textfont: { color: INK_2, size: 10 },
            marker: { size: 11, color: t.max_partner_vs_opponent.map((p) => p.level), colorscale: SEQUENTIAL, line: { color: SURFACE, width: 2 } },
            hovertemplate: '<b>%{text}</b><br>max partner %{x}<br>max opponent %{y}<extra></extra>',
          },
        ]}
        layout={baseLayout({ xaxis: axis('Max partner level'), yaxis: axis('Max opponent level') })}
      />
    </Panel>
  )
}
