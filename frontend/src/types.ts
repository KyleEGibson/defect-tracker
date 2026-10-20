export type Role = 'viewer' | 'engineer' | 'lead' | 'admin'
export type Severity = 'critical' | 'major' | 'minor'
export type Status =
  | 'open'
  | 'investigating'
  | 'root_cause_identified'
  | 'corrective_action'
  | 'verification'
  | 'closed'
  | 'rejected'
export type TestStage = 'unit' | 'integration' | 'system' | 'acceptance' | 'field'
export type RootCause =
  | 'design'
  | 'software'
  | 'material'
  | 'workmanship'
  | 'test_equipment'
  | 'process'
  | 'environment'
  | 'documentation'

export const STATUS_ORDER: Status[] = [
  'open',
  'investigating',
  'root_cause_identified',
  'corrective_action',
  'verification',
  'closed',
  'rejected',
]

export const STATUS_LABEL: Record<Status, string> = {
  open: 'Open',
  investigating: 'Investigating',
  root_cause_identified: 'Root cause identified',
  corrective_action: 'Corrective action',
  verification: 'Verification',
  closed: 'Closed',
  rejected: 'Rejected',
}

export const ROOT_CAUSES: RootCause[] = [
  'design',
  'software',
  'material',
  'workmanship',
  'test_equipment',
  'process',
  'environment',
  'documentation',
]

export interface User {
  username: string
  full_name: string
  role: Role
}

export interface Action {
  id: number
  description: string
  owner: string
  due_date: string | null
  done: boolean
  completed_at: string | null
}

export interface Defect {
  key: string
  title: string
  description: string
  severity: Severity
  status: Status
  product: string
  component: string
  failure_mode: string
  found_in: TestStage
  reporter: string
  assignee: string | null
  root_cause_category: RootCause | null
  root_cause: string
  verification_notes: string
  created_at: string
  updated_at: string
  closed_at: string | null
  actions: Action[]
}

export interface DefectSummary {
  key: string
  title: string
  severity: Severity
  status: Status
  product: string
  failure_mode: string
  assignee: string | null
  created_at: string
  age_days: number
}

export interface DefectPage {
  items: DefectSummary[]
  total: number
  page: number
  page_size: number
}

export interface TransitionOption {
  to: Status
  allowed: boolean
  problems: string[]
}

export interface AuditEvent {
  action: string
  actor: string
  from_status: string | null
  to_status: string | null
  details: string
  at: string
}

export interface Metrics {
  total: number
  open: number
  by_status: Record<string, number>
  open_by_severity: Record<string, number>
  pareto: { failure_mode: string; count: number; cumulative_pct: number }[]
  root_causes: Record<string, number>
  aging: Record<string, number>
  mean_days_to_close: number | null
  weekly: { week: string; opened: number; closed: number }[]
}
