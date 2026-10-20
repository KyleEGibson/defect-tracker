// Plain SVG charts, no chart library. Colors are CSS vars so dark mode just works.

import type { ReactNode } from 'react'

export function ChartCard({ title, children, table }: { title: string; children: ReactNode; table: ReactNode }) {
  return (
    <section className="card chart-card">
      <h3>{title}</h3>
      {children}
      <details>
        <summary>Table view</summary>
        {table}
      </details>
    </section>
  )
}

interface Bar {
  label: string
  value: number
}

export function BarChart({ data, unit = '' }: { data: Bar[]; unit?: string }) {
  const max = Math.max(1, ...data.map((d) => d.value))
  const rowHeight = 28
  const labelWidth = 190
  const width = 560
  const plot = width - labelWidth - 48
  return (
    <svg className="chart" viewBox={`0 0 ${width} ${data.length * rowHeight + 8}`} role="img"
         aria-label={data.map((d) => `${d.label} ${d.value}${unit}`).join(', ')}>
      {data.map((d, i) => {
        const w = Math.max(2, (d.value / max) * plot)
        const y = i * rowHeight + 4
        return (
          <g key={d.label}>
            <text x={labelWidth - 8} y={y + 15} textAnchor="end" className="axis-label">
              {d.label.length > 28 ? `${d.label.slice(0, 27)}…` : d.label}
            </text>
            <rect x={labelWidth} y={y + 3} width={w} height={rowHeight - 10} rx={4} className="bar">
              <title>{`${d.label}: ${d.value}${unit}`}</title>
            </rect>
            <text x={labelWidth + w + 6} y={y + 15} className="value-label">
              {d.value}
              {unit}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

interface Series {
  name: string
  values: number[]
  className: string
}

export function LineChart({ labels, series }: { labels: string[]; series: Series[] }) {
  const width = 560
  const height = 220
  const pad = { left: 36, right: 12, top: 12, bottom: 28 }
  const max = Math.max(1, ...series.flatMap((s) => s.values))
  const x = (i: number) => pad.left + (i * (width - pad.left - pad.right)) / Math.max(1, labels.length - 1)
  const y = (v: number) => pad.top + (1 - v / max) * (height - pad.top - pad.bottom)
  const ticks = [0, Math.round(max / 2), max]
  return (
    <>
      <div className="legend">
        {series.map((s) => (
          <span key={s.name} className="legend-item">
            <span className={`swatch ${s.className}`} /> {s.name}
          </span>
        ))}
      </div>
      <svg className="chart" viewBox={`0 0 ${width} ${height}`} role="img"
           aria-label={series.map((s) => `${s.name}: ${s.values.join(', ')}`).join('; ')}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={width - pad.right} y1={y(t)} y2={y(t)} className="grid" />
            <text x={pad.left - 6} y={y(t) + 4} textAnchor="end" className="axis-label">{t}</text>
          </g>
        ))}
        {labels.map((label, i) =>
          i % 2 === 0 ? (
            <text key={label} x={x(i)} y={height - 8} textAnchor="middle" className="axis-label">{label}</text>
          ) : null,
        )}
        {series.map((s) => (
          <g key={s.name} className={s.className}>
            <polyline fill="none" className="line" points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(' ')} />
            {s.values.map((v, i) => (
              <circle key={i} cx={x(i)} cy={y(v)} r={4} className="point">
                <title>{`${s.name}, week of ${labels[i]}: ${v}`}</title>
              </circle>
            ))}
          </g>
        ))}
      </svg>
    </>
  )
}
