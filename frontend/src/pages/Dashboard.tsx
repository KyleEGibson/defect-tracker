import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { BarChart, ChartCard, LineChart } from '../components/Charts'
import type { Metrics } from '../types'

function SimpleTable({ rows, headers }: { rows: (string | number)[][]; headers: string[] }) {
  return (
    <table>
      <thead><tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r) => <tr key={String(r[0])}>{r.map((c, i) => <td key={i} className={typeof c === 'number' ? 'num' : ''}>{c}</td>)}</tr>)}</tbody>
    </table>
  )
}

export function Dashboard() {
  const [m, setM] = useState<Metrics | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.metrics().then(setM).catch(() => setError('Failed to load metrics'))
  }, [])

  if (error) return <p className="error" role="alert">{error}</p>
  if (!m) return <p className="muted">Loading…</p>

  const weeks = m.weekly.map((w) => w.week.slice(5))
  return (
    <>
      <h1>Quality dashboard</h1>
      <div className="tiles">
        <Link className="tile" to="/defects?status=open"><span className="v">{m.open}</span><span className="l">open defects</span></Link>
        <div className="tile"><span className="v">{m.open_by_severity.critical ?? 0}</span><span className="l">open critical</span></div>
        <div className="tile"><span className="v">{m.mean_days_to_close ?? '-'}</span><span className="l">mean days to close</span></div>
        <div className="tile"><span className="v">{m.by_status.verification ?? 0}</span><span className="l">awaiting verification</span></div>
      </div>
      <div className="chart-grid">
        <ChartCard title="Failure Pareto (top 10)"
                   table={<SimpleTable headers={['Failure mode', 'Count', 'Cumulative %']}
                                       rows={m.pareto.map((p) => [p.failure_mode, p.count, p.cumulative_pct])} />}>
          <BarChart data={m.pareto.map((p) => ({ label: p.failure_mode, value: p.count }))} />
        </ChartCard>
        <ChartCard title="Opened vs closed per week"
                   table={<SimpleTable headers={['Week', 'Opened', 'Closed']} rows={m.weekly.map((w) => [w.week, w.opened, w.closed])} />}>
          <LineChart labels={weeks} series={[
            { name: 'Opened', values: m.weekly.map((w) => w.opened), className: 's1' },
            { name: 'Closed', values: m.weekly.map((w) => w.closed), className: 's2' },
          ]} />
        </ChartCard>
        <ChartCard title="Root cause categories"
                   table={<SimpleTable headers={['Category', 'Defects']} rows={Object.entries(m.root_causes)} />}>
          <BarChart data={Object.entries(m.root_causes).map(([label, value]) => ({ label: label.replace('_', ' '), value }))} />
        </ChartCard>
        <ChartCard title="Open defect age"
                   table={<SimpleTable headers={['Age', 'Open defects']} rows={Object.entries(m.aging)} />}>
          <BarChart data={Object.entries(m.aging).map(([label, value]) => ({ label, value }))} />
        </ChartCard>
      </div>
    </>
  )
}
