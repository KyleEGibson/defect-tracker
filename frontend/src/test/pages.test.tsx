import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Defects } from '../pages/Defects'

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
}

function LocationProbe() {
  return <span data-testid="location">{useLocation().search}</span>
}

const page = {
  items: [{ key: 'DEF-0007', title: 'Slew time exceeds 2.0 s', severity: 'critical', status: 'investigating',
            product: 'EOS-100', failure_mode: 'Slew time', assignee: 'kgibson', created_at: '2026-10-01T00:00:00Z',
            age_days: 14 }],
  total: 41, page: 1, page_size: 20,
}

describe('Defects page', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists defects and puts filters in the URL', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(page)))
    vi.stubGlobal('fetch', fetchMock)
    render(
      <MemoryRouter initialEntries={['/defects']}>
        <Routes><Route path="/defects" element={<><Defects /><LocationProbe /></>} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('link', { name: 'DEF-0007' })).toHaveAttribute('href', '/defects/DEF-0007')
    expect(screen.getByText('Page 1 of 3 · 41 defects')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Status'), 'investigating')
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('?status=investigating'))
    await waitFor(() => expect(fetchMock.mock.calls.at(-1)?.[0]).toContain('status=investigating'))

    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('page=2'))
  })

  it('shows an error instead of an empty table when loading fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"boom"}', { status: 500 })))
    render(<MemoryRouter><Defects /></MemoryRouter>)
    expect(await screen.findByRole('alert')).toHaveTextContent('boom')
  })
})
