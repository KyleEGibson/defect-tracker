import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../useAuth'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { TransitionPanel } from '../components/TransitionPanel'
import { ROOT_CAUSES, STATUS_LABEL, type AuditEvent, type Defect, type Status, type TransitionOption, type User } from '../types'

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

function describeEvent(e: AuditEvent): string {
  if (e.action === 'transition') {
    const reason = e.details ? JSON.parse(e.details).reason : ''
    return `moved ${STATUS_LABEL[e.from_status as Status]} to ${STATUS_LABEL[e.to_status as Status]}${reason ? ` ("${reason}")` : ''}`
  }
  if (e.action === 'created') return 'reported the defect'
  if (e.action === 'updated') return `changed ${Object.keys(JSON.parse(e.details || '{}')).join(', ').replaceAll('_', ' ')}`
  if (e.action === 'action_added') return `added corrective action "${JSON.parse(e.details).description}"`
  if (e.action === 'action_completed') return 'completed a corrective action'
  return e.action
}

export function DefectDetail() {
  const { key = '' } = useParams()
  const { can } = useAuth()
  const [defect, setDefect] = useState<Defect | null>(null)
  const [options, setOptions] = useState<TransitionOption[]>([])
  const [history, setHistory] = useState<AuditEvent[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [error, setError] = useState<{ message: string; problems: string[] } | null>(null)
  const [draft, setDraftState] = useState({ root_cause_category: '', root_cause: '', verification_notes: '', assignee: '' })
  // don't clobber unsaved edits when we reload after a workflow move
  const dirty = useRef(false)
  const setDraft = (next: typeof draft) => {
    dirty.current = true
    setDraftState(next)
  }
  const [action, setAction] = useState({ description: '', owner: '' })

  const load = useCallback(() => Promise.all([api.getDefect(key), api.transitions(key), api.history(key)]), [key])

  const apply = useCallback(([d, o, h]: [Defect, TransitionOption[], AuditEvent[]]) => {
    setDefect(d)
    setOptions(o)
    setHistory(h)
    if (!dirty.current) {
      setDraftState({ root_cause_category: d.root_cause_category ?? '', root_cause: d.root_cause,
                      verification_notes: d.verification_notes, assignee: d.assignee ?? '' })
    }
  }, [])

  const reload = useCallback(async () => apply(await load()), [load, apply])

  useEffect(() => {
    // drop responses for a defect we've already navigated away from
    let cancelled = false
    dirty.current = false
    load()
      .then((data) => { if (!cancelled) apply(data) })
      .catch((err) => { if (!cancelled) setError({ message: err instanceof ApiError ? err.message : 'Failed to load', problems: [] }) })
    api.users()
      .then((all) => { if (!cancelled) setUsers(all) })
      .catch(() => { if (!cancelled) setUsers([]) })
    return () => { cancelled = true }
  }, [load, apply])

  async function run(task: () => Promise<unknown>) {
    setError(null)
    try {
      await task()
      await reload()
    } catch (err) {
      if (err instanceof ApiError) setError({ message: err.message, problems: err.problems })
      else throw err
    }
  }

  if (!defect) return error ? <p className="error" role="alert">{error.message}</p> : <p className="muted">Loading…</p>

  const editable = can('engineer') && defect.status !== 'closed' && defect.status !== 'rejected'
  const engineers = users.filter((u) => u.role !== 'viewer')

  function save(event: FormEvent) {
    event.preventDefault()
    dirty.current = false
    void run(() => api.updateDefect(key, {
      ...(draft.root_cause_category ? { root_cause_category: draft.root_cause_category } : {}),
      root_cause: draft.root_cause,
      verification_notes: draft.verification_notes,
      ...(draft.assignee ? { assignee: draft.assignee } : {}),
    }))
  }

  return (
    <>
      <div className="detail-head">
        <span className="key">{defect.key}</span>
        <h1>{defect.title}</h1>
        <div className="chips"><StatusBadge status={defect.status} /><SeverityBadge severity={defect.severity} /></div>
      </div>

      {error && (
        <div className="error" role="alert">
          {error.message}
          {error.problems.length > 0 && <ul>{error.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
        </div>
      )}

      <div className="detail-grid">
        <section className="card">
          <h2>Details</h2>
          <dl className="facts">
            <dt>Product</dt><dd>{defect.product} / {defect.component}</dd>
            <dt>Failure mode</dt><dd>{defect.failure_mode}</dd>
            <dt>Found in</dt><dd>{defect.found_in} test</dd>
            <dt>Reported by</dt><dd>{defect.reporter} · {when(defect.created_at)}</dd>
            {defect.closed_at && <><dt>Closed</dt><dd>{when(defect.closed_at)}</dd></>}
          </dl>
          <p className="description">{defect.description || <span className="muted">No description.</span>}</p>
        </section>

        <section className="card">
          <h2>Workflow</h2>
          {can('engineer') ? (
            <TransitionPanel current={defect.status} options={options}
                             onMove={(to, reason) => run(() => api.transition(key, to, reason))} />
          ) : (
            <p className="muted">Read-only access.</p>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Investigation</h2>
        <form className="investigation" onSubmit={save}>
          <label>Assignee
            <select value={draft.assignee} disabled={!editable} onChange={(e) => setDraft({ ...draft, assignee: e.target.value })}>
              <option value="">Unassigned</option>
              {engineers.map((u) => <option key={u.username} value={u.username}>{u.full_name}</option>)}
            </select>
          </label>
          <label>Root cause category
            <select value={draft.root_cause_category} disabled={!editable}
                    onChange={(e) => setDraft({ ...draft, root_cause_category: e.target.value })}>
              <option value="">Not yet determined</option>
              {ROOT_CAUSES.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
            </select>
          </label>
          <label className="wide">Root cause
            <textarea rows={3} value={draft.root_cause} disabled={!editable}
                      onChange={(e) => setDraft({ ...draft, root_cause: e.target.value })} />
          </label>
          <label className="wide">Verification evidence
            <textarea rows={2} value={draft.verification_notes} disabled={!editable}
                      onChange={(e) => setDraft({ ...draft, verification_notes: e.target.value })} />
          </label>
          {editable && <button type="submit" className="primary">Save investigation</button>}
        </form>
      </section>

      <section className="card">
        <h2>Corrective actions</h2>
        {defect.actions.length === 0 && <p className="muted">None yet.</p>}
        <ul className="actions">
          {defect.actions.map((a) => (
            <li key={a.id} className={a.done ? 'done' : ''}>
              <span>{a.done ? '✔' : '○'} {a.description}</span>
              <span className="muted">{a.owner}{a.due_date ? ` · due ${a.due_date}` : ''}</span>
              {!a.done && defect.status === 'corrective_action' && can('engineer') && (
                <button type="button" className="secondary" onClick={() => run(() => api.completeAction(key, a.id))}>
                  Mark complete
                </button>
              )}
            </li>
          ))}
        </ul>
        {can('engineer') && (defect.status === 'root_cause_identified' || defect.status === 'corrective_action') && (
          <form className="add-action" onSubmit={(e) => {
            e.preventDefault()
            void run(() => api.addAction(key, action)).then(() => setAction({ description: '', owner: '' }))
          }}>
            <input aria-label="Action description" placeholder="Describe the corrective action" required minLength={5}
                   value={action.description} onChange={(e) => setAction({ ...action, description: e.target.value })} />
            <select aria-label="Action owner" required value={action.owner} onChange={(e) => setAction({ ...action, owner: e.target.value })}>
              <option value="">Owner…</option>
              {engineers.map((u) => <option key={u.username} value={u.username}>{u.full_name}</option>)}
            </select>
            <button type="submit" className="secondary">Add action</button>
          </form>
        )}
      </section>

      <section className="card">
        <h2>History</h2>
        <ol className="timeline">
          {history.map((e, i) => (
            <li key={i}><strong>{e.actor}</strong> {describeEvent(e)} <span className="muted">· {when(e.at)}</span></li>
          ))}
        </ol>
      </section>
    </>
  )
}
