import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api'
import type { User } from '../types'

const EMPTY = { title: '', description: '', severity: 'major', product: 'EOS-100', component: '',
                failure_mode: '', found_in: 'acceptance', assignee: '' }

export function NewDefect() {
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY)
  const [users, setUsers] = useState<User[]>([])
  const [error, setError] = useState<{ message: string; problems: string[] } | null>(null)

  useEffect(() => {
    api.users().then((all) => setUsers(all.filter((u) => u.role !== 'viewer'))).catch(() => setUsers([]))
  }, [])

  const field = (name: keyof typeof EMPTY) => ({
    value: form[name],
    onChange: (e: { target: { value: string } }) => setForm({ ...form, [name]: e.target.value }),
  })

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    try {
      const created = await api.createDefect({ ...form, assignee: form.assignee || undefined })
      navigate(`/defects/${created.key}`)
    } catch (err) {
      if (err instanceof ApiError) setError({ message: err.message, problems: err.problems })
      else throw err
    }
  }

  return (
    <>
      <h1>Report a defect</h1>
      <form className="card form-grid" onSubmit={submit}>
        <label className="wide">Title<input required minLength={5} maxLength={200} {...field('title')} /></label>
        <label>Severity
          <select {...field('severity')}>
            <option value="critical">Critical</option><option value="major">Major</option><option value="minor">Minor</option>
          </select>
        </label>
        <label>Found in
          <select {...field('found_in')}>
            {['unit', 'integration', 'system', 'acceptance', 'field'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <label>Product<input required {...field('product')} /></label>
        <label>Component<input required {...field('component')} /></label>
        <label className="wide">Failure mode<input required placeholder="e.g. Slew time exceeds 2.0 s" {...field('failure_mode')} /></label>
        <label className="wide">Description<textarea rows={4} {...field('description')} /></label>
        <label>Assignee
          <select {...field('assignee')}>
            <option value="">Unassigned</option>
            {users.map((u) => <option key={u.username} value={u.username}>{u.full_name}</option>)}
          </select>
        </label>
        {error && (
          <div className="error wide" role="alert">
            {error.message}
            {error.problems.length > 0 && <ul>{error.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
          </div>
        )}
        <div className="wide"><button type="submit" className="primary">Create defect</button></div>
      </form>
    </>
  )
}
