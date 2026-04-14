const DECISION_STYLES = {
  APPROVED:      'bg-green-100 text-green-800',
  REJECTED:      'bg-red-100 text-red-800',
  MANUAL_REVIEW: 'bg-yellow-100 text-yellow-800',
  PENDING:       'bg-gray-100 text-gray-600',
}

const STATUS_STYLES = {
  DRAFT:        'bg-gray-100 text-gray-600',
  SUBMITTED:    'bg-blue-100 text-blue-800',
  UNDER_REVIEW: 'bg-yellow-100 text-yellow-800',
  COMPLETED:    'bg-green-100 text-green-800',
  REJECTED:     'bg-red-100 text-red-800',
}

export function DecisionBadge({ decision }) {
  const style = DECISION_STYLES[decision] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {decision || 'PENDING'}
    </span>
  )
}

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {status || '—'}
    </span>
  )
}
