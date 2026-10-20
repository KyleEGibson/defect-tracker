import { STATUS_ORDER, type Status } from './types'

// same rule as backend/app/workflow.py: going backwards needs a reason
export function isBackward(current: Status, to: Status): boolean {
  return to === 'rejected' || STATUS_ORDER.indexOf(to) < STATUS_ORDER.indexOf(current)
}
