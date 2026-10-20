import { useState } from 'react'
import { STATUS_LABEL, type Status, type TransitionOption } from '../types'
import { isBackward } from '../workflow'

interface Props {
  current: Status
  options: TransitionOption[]
  onMove: (to: Status, reason: string) => Promise<void>
}

// the server decides what's allowed; this just shows its reasons
export function TransitionPanel({ current, options, onMove }: Props) {
  const [reasons, setReasons] = useState<Partial<Record<Status, string>>>({})
  const [busy, setBusy] = useState(false)

  if (options.length === 0) return null
  return (
    <div className="transitions">
      {options.map((option) => {
        const needsReason = isBackward(current, option.to)
        const reason = reasons[option.to] ?? ''
        const ready = option.allowed && (!needsReason || reason.trim().length > 0)
        return (
          <div key={option.to} className="transition">
            <button
              type="button"
              className={needsReason ? 'secondary' : 'primary'}
              disabled={!ready || busy}
              onClick={async () => {
                setBusy(true)
                try {
                  await onMove(option.to, reason)
                  setReasons({})
                } finally {
                  setBusy(false)
                }
              }}
            >
              {needsReason ? 'Back to ' : 'Move to '}
              {STATUS_LABEL[option.to]}
            </button>
            {needsReason && option.allowed && (
              <input
                aria-label={`Reason for ${STATUS_LABEL[option.to]}`}
                placeholder="Reason (required)"
                value={reason}
                onChange={(e) => setReasons({ ...reasons, [option.to]: e.target.value })}
              />
            )}
            {option.problems.length > 0 && (
              <ul className="problems">
                {option.problems.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </div>
  )
}
