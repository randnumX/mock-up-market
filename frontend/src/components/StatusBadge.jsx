const SOURCE_LABELS = {
  kite: 'Zerodha Live Data',
  mongodb: 'MongoDB Connected',
  generated: 'Using Generated Data',
}

export default function StatusBadge({ health }) {
  if (!health) return null

  const source = health.data_source || 'generated'
  const isReal = source !== 'generated'
  const label = SOURCE_LABELS[source] || 'Using Generated Data'

  return (
    <div className="status-badge">
      <span className={`status-dot ${isReal ? 'online' : 'offline'}`} />
      <span>{label}</span>
    </div>
  )
}
