import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, request, setUnauthorizedHandler, tokenStore } from '../api'

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
}

describe('api client', () => {
  beforeEach(() => tokenStore.set('abc.def.ghi'))
  afterEach(() => {
    vi.unstubAllGlobals()
    tokenStore.set(null)
  })

  it('sends the bearer token and builds query strings with repeated keys', async () => {
    const fetchMock = respond(200, { items: [], total: 0, page: 1, page_size: 20 })
    vi.stubGlobal('fetch', fetchMock)
    await api.listDefects({ status: ['open', 'closed'], q: 'slew', page: 2, severity: undefined })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/defects?status=open&status=closed&q=slew&page=2')
    expect(init.headers.Authorization).toBe('Bearer abc.def.ghi')
  })

  it('clears the session and notifies on 401', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    vi.stubGlobal('fetch', respond(401, { detail: 'Not authenticated' }))
    await expect(api.me()).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledOnce()
    expect(tokenStore.get()).toBeNull()
  })

  it('does not treat a failed login as an expired session', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    vi.stubGlobal('fetch', respond(401, { detail: 'Incorrect username or password' }))
    await expect(api.login('a', 'b')).rejects.toThrow('Incorrect username or password')
    expect(handler).not.toHaveBeenCalled()
  })

  it('surfaces workflow problems from a 409', async () => {
    vi.stubGlobal('fetch', respond(409, { detail: { message: 'transition not allowed', problems: ['record verification evidence'] } }))
    const error = (await request('/defects/DEF-0001/transition', { method: 'POST', json: {} }).catch((e) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(409)
    expect(error.problems).toEqual(['record verification evidence'])
  })

  it('turns validation errors into readable field messages', async () => {
    vi.stubGlobal('fetch', respond(422, { detail: [{ loc: ['body', 'title'], msg: 'String should have at least 5 characters' }] }))
    const error = (await api.createDefect({}).catch((e) => e)) as ApiError
    expect(error.problems).toEqual(['title: String should have at least 5 characters'])
  })

  it('posts login as a form, not JSON', async () => {
    const fetchMock = respond(200, { access_token: 't', user: { username: 'eng', full_name: 'E', role: 'engineer' } })
    vi.stubGlobal('fetch', fetchMock)
    await api.login('eng', 'secret')
    const init = fetchMock.mock.calls[0][1]
    expect(init.body).toBeInstanceOf(URLSearchParams)
    expect(String(init.body)).toBe('username=eng&password=secret')
  })
})
