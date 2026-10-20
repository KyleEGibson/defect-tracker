import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SeverityBadge, StatusBadge } from '../components/Badges'
import { BarChart } from '../components/Charts'
import { TransitionPanel } from '../components/TransitionPanel'
import { isBackward } from '../workflow'

describe('badges', () => {
  it('always shows text, not only color', () => {
    render(<><StatusBadge status="root_cause_identified" /><SeverityBadge severity="critical" /></>)
    expect(screen.getByText('Root cause identified')).toBeInTheDocument()
    expect(screen.getByText(/critical/)).toBeInTheDocument()
  })
})

describe('TransitionPanel', () => {
  it('knows which moves are backward', () => {
    expect(isBackward('verification', 'corrective_action')).toBe(true)
    expect(isBackward('open', 'rejected')).toBe(true)
    expect(isBackward('open', 'investigating')).toBe(false)
  })

  it('disables blocked moves and lists why', () => {
    render(
      <TransitionPanel current="investigating" onMove={vi.fn()} options={[
        { to: 'root_cause_identified', allowed: false, problems: ['record the root cause category and description'] },
      ]} />,
    )
    expect(screen.getByRole('button', { name: /Root cause identified/ })).toBeDisabled()
    expect(screen.getByText('record the root cause category and description')).toBeInTheDocument()
  })

  it('requires a reason before a backward move', async () => {
    const onMove = vi.fn().mockResolvedValue(undefined)
    render(
      <TransitionPanel current="verification" onMove={onMove} options={[
        { to: 'closed', allowed: true, problems: [] },
        { to: 'corrective_action', allowed: true, problems: [] },
      ]} />,
    )
    const back = screen.getByRole('button', { name: /Corrective action/ })
    expect(back).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Reason for Corrective action'), 'Unit 4 still slow')
    expect(back).toBeEnabled()
    await userEvent.click(back)
    expect(onMove).toHaveBeenCalledWith('corrective_action', 'Unit 4 still slow')

    await userEvent.click(screen.getByRole('button', { name: /Closed/ }))
    expect(onMove).toHaveBeenLastCalledWith('closed', '')
  })
})

describe('BarChart', () => {
  it('scales bars to the largest value and labels every bar', () => {
    const { container } = render(<BarChart data={[{ label: 'Slew time', value: 10 }, { label: 'CRC', value: 5 }]} />)
    const bars = container.querySelectorAll('rect.bar')
    expect(Number(bars[0].getAttribute('width'))).toBeCloseTo(2 * Number(bars[1].getAttribute('width')))
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(container.querySelector('svg')?.getAttribute('aria-label')).toBe('Slew time 10, CRC 5')
  })
})
