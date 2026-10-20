import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { STATUS_LABEL, STATUS_ORDER, type DefectPage } from '../types'

const PAGE_SIZE = 20

// filters live in the URL so a filtered list can be bookmarked
export function Defects() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<DefectPage | null>(null)
  const [error, setError] = useState('')
  const status = params.get('status') ?? ''
  const severity = params.get('severity') ?? ''
  const q = params.get('q') ?? ''
  const page = Number(params.get('page') ?? '1')
  const [search, setSearch] = useState(q)

  useEffect(() => {
    let cancelled = false
    api
      .listDefects({ status: status || undefined, severity: severity || undefined, q: q || undefined, page, page_size: PAGE_SIZE })
      .then((result) => !cancelled && (setData(result), setError('')))
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.message : 'Failed to load defects'))
    return () => {
      cancelled = true
    }
  }, [status, severity, q, page])

  function update(changes: Record<string, string>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    if (!('page' in changes)) next.delete('page')
    setParams(next)
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1
  return (
    <>
      <h1>Defects</h1>
      <form className="filters" onSubmit={(e) => { e.preventDefault(); update({ q: search }) }}>
        <select aria-label="Status" value={status} onChange={(e) => update({ status: e.target.value })}>
          <option value="">All statuses</option>
          {STATUS_ORDER.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
        <select aria-label="Severity" value={severity} onChange={(e) => update({ severity: e.target.value })}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
        </select>
        <input type="search" aria-label="Search" placeholder="Search title or failure mode"
               value={search} onChange={(e) => setSearch(e.target.value)} />
        <button type="submit" className="secondary">Search</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {data && (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr><th>Key</th><th>Title</th><th>Severity</th><th>Status</th><th>Assignee</th><th className="num">Age (days)</th></tr>
            </thead>
            <tbody>
              {data.items.map((d) => (
                <tr key={d.key}>
                  <td><Link to={`/defects/${d.key}`}>{d.key}</Link></td>
                  <td>{d.title}</td>
                  <td><SeverityBadge severity={d.severity} /></td>
                  <td><StatusBadge status={d.status} /></td>
                  <td>{d.assignee ?? <span className="muted">unassigned</span>}</td>
                  <td className="num">{d.age_days}</td>
                </tr>
              ))}
              {data.items.length === 0 && <tr><td colSpan={6} className="muted">No defects match these filters.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      {data && (
        <div className="pager">
          <button type="button" className="secondary" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</button>
          <span>Page {page} of {pages} · {data.total} defects</span>
          <button type="button" className="secondary" disabled={page >= pages} onClick={() => update({ page: String(page + 1) })}>Next</button>
        </div>
      )}
    </>
  )
}
