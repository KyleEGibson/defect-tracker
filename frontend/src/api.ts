import type {
  Action,
  AuditEvent,
  Defect,
  DefectPage,
  Metrics,
  Status,
  TransitionOption,
  User,
} from './types'

const TOKEN_KEY = 'tracker.token'

export class ApiError extends Error {
  readonly status: number
  readonly problems: string[]

  constructor(status: number, message: string, problems: string[] = []) {
    super(message)
    this.status = status
    this.problems = problems
  }
}

// sessionStorage so the token dies with the tab. It can throw in private mode.
export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string | null) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token)
      else sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* the session simply won't survive a reload */
    }
  },
}

let onUnauthorized: () => void = () => {}
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

type Params = Record<string, string | number | string[] | undefined>

function query(params?: Params): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value === undefined || value === '') continue
    for (const v of Array.isArray(value) ? value : [value]) search.append(key, String(v))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

function describe(detail: unknown): { message: string; problems: string[] } {
  if (typeof detail === 'string') return { message: detail, problems: [] }
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [...], msg}]
    const problems = detail.map((d: { loc?: unknown[]; msg?: string }) =>
      `${(d.loc ?? []).slice(1).join('.')}: ${d.msg ?? 'invalid'}`)
    return { message: 'Please correct the highlighted fields', problems }
  }
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const d = detail as { message: string; problems?: string[] }
    return { message: d.message, problems: d.problems ?? [] }
  }
  return { message: 'Request failed', problems: [] }
}

export async function request<T>(
  path: string,
  options: { method?: string; json?: unknown; form?: Record<string, string>; params?: Params } = {},
): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  } else if (options.form) {
    body = new URLSearchParams(options.form)
  }
  const response = await fetch(`/api${path}${query(options.params)}`, { method: options.method ?? 'GET', headers, body })
  if (response.status === 401 && !path.startsWith('/auth/')) {
    tokenStore.set(null)
    onUnauthorized()
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const { message, problems } = describe((payload as { detail?: unknown }).detail)
    throw new ApiError(response.status, message, problems)
  }
  return (await response.json()) as T
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; user: User }>('/auth/token', { method: 'POST', form: { username, password } }),
  me: () => request<User>('/users/me'),
  users: () => request<User[]>('/users'),
  listDefects: (params: Params) => request<DefectPage>('/defects', { params }),
  getDefect: (key: string) => request<Defect>(`/defects/${key}`),
  createDefect: (body: Record<string, unknown>) => request<Defect>('/defects', { method: 'POST', json: body }),
  updateDefect: (key: string, body: Record<string, unknown>) =>
    request<Defect>(`/defects/${key}`, { method: 'PATCH', json: body }),
  transitions: (key: string) => request<TransitionOption[]>(`/defects/${key}/transitions`),
  transition: (key: string, to: Status, reason: string) =>
    request<Defect>(`/defects/${key}/transition`, { method: 'POST', json: { to, reason } }),
  addAction: (key: string, body: { description: string; owner: string; due_date?: string }) =>
    request<Action>(`/defects/${key}/actions`, { method: 'POST', json: body }),
  completeAction: (key: string, id: number) =>
    request<Action>(`/defects/${key}/actions/${id}/complete`, { method: 'POST' }),
  history: (key: string) => request<AuditEvent[]>(`/defects/${key}/history`),
  metrics: () => request<Metrics>('/metrics'),
}
