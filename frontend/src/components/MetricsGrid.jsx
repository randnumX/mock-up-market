export default function MetricsGrid({ results }) {
  if (!results) return null

  const metrics = [
    {
      label: 'Net ROI',
      value: `${results.roi >= 0 ? '+' : ''}${results.roi}%`,
      className: results.roi >= 0 ? 'positive' : 'negative',
      sub: `${results.total_trades} trades executed`,
    },
    {
      label: 'Net Profit',
      value: `₹${results.realized_pnl.toLocaleString('en-IN')}`,
      className: results.realized_pnl >= 0 ? 'positive' : 'negative',
      sub: `Win rate: ${results.win_rate}%`,
    },
    {
      label: 'Taxes & Charges',
      value: `₹${results.total_taxes.toLocaleString('en-IN')}`,
      className: 'negative',
      sub: 'STT + GST + Stamp + SEBI',
    },
    {
      label: 'Final Capital',
      value: `₹${results.final_capital.toLocaleString('en-IN')}`,
      className: 'accent',
      sub: results.open_position_value > 0
        ? `Incl. ₹${results.open_position_value.toLocaleString('en-IN')} open position`
        : `Max Drawdown: ${results.max_drawdown}%`,
    },
  ]

  return (
    <div className="metrics-grid animate-in">
      {metrics.map((m, i) => (
        <div
          key={m.label}
          className="metric-card"
          style={{ animationDelay: `${i * 0.1}s` }}
        >
          <div className="metric-label">{m.label}</div>
          <div className={`metric-value ${m.className}`}>{m.value}</div>
          {m.sub && <div className="metric-sub">{m.sub}</div>}
        </div>
      ))}
    </div>
  )
}
