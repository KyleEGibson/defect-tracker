import { STATUS_LABEL, type Severity, type Status } from '../types'

// always show the text too, not just a color
export function StatusBadge({ status }: { status: Status }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status]}</span>
}

const SEVERITY_ICON: Record<Severity, string> = { critical: '▲', major: '■', minor: '●' }

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`severity sev-${severity}`}>
      <span aria-hidden="true">{SEVERITY_ICON[severity]}</span> {severity}
    </span>
  )
}
