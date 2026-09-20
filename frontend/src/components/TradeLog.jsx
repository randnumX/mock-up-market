import { fmtINR, signedINR } from '../utils/format'

export default function TradeLog({ results, drilldownTicker = 'ALL' }) {
  if (!results || !results.trades || results.trades.length === 0) return null

  const isDrilldown = drilldownTicker !== 'ALL'
  const allTrades = [...results.trades].reverse()
  const trades = isDrilldown 
    ? allTrades.filter(t => t.symbol === drilldownTicker)
    : allTrades

  const formatDate = (ts) => {
    if (!ts || ts === 'None') return '—'
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
  }

  return (
    <div className="glass-card animate-in">
      <div className="card-title">
        {isDrilldown ? `Trade Log: ${drilldownTicker}` : 'Portfolio Trade Log'} 
        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 'normal', marginLeft: '0.5rem' }}>
          ({trades.length} orders)
        </span>
      </div>
      <div className="trade-log-wrapper">
        <table className="trade-table">
          <thead>
            <tr>
              <th>Date</th>
              {!isDrilldown && <th>Symbol</th>}
              <th>Type</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Taxes</th>
              <th>PnL</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr key={i}>
                <td>{formatDate(t.timestamp)}</td>
                {!isDrilldown && (
                  <td style={{ fontWeight: 500, color: 'var(--brand-blue)' }}>{t.symbol || '—'}</td>
                )}
                <td>
                  <span className={`trade-type ${t.type.toLowerCase()}`}>
                    {t.type}
                  </span>
                </td>
                <td>{t.qty}</td>
                <td>{fmtINR(t.price)}</td>
                <td>{t.taxes !== undefined ? fmtINR(t.taxes) : '—'}</td>
                <td className={t.pnl !== undefined ? (t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative') : ''}>
                  {t.pnl !== undefined ? signedINR(t.pnl) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
