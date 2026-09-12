export default function TradeLog({ results }) {
  if (!results || !results.trades || results.trades.length === 0) return null

  const trades = [...results.trades].reverse()

  const formatDate = (ts) => {
    if (!ts || ts === 'None') return '—'
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' })
  }

  return (
    <div className="glass-card animate-in">
      <div className="card-title">Trade Log ({results.trades.length} orders)</div>
      <div className="trade-log-wrapper">
        <table className="trade-table">
          <thead>
            <tr>
              <th>Date</th>
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
                <td>
                  <span className={`trade-type ${t.type.toLowerCase()}`}>
                    {t.type}
                  </span>
                </td>
                <td>{t.qty}</td>
                <td>₹{t.price.toFixed(2)}</td>
                <td>{t.taxes !== undefined ? `₹${t.taxes.toFixed(2)}` : '—'}</td>
                <td className={t.pnl !== undefined ? (t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative') : ''}>
                  {t.pnl !== undefined ? `₹${t.pnl.toFixed(2)}` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
