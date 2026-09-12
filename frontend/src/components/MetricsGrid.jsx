import { fmtINR, signedINR } from '../utils/format'

function StreamingMetrics({ results, progress }) {
  const lastPoint = results.equity_curve[results.equity_curve.length - 1]
  const equity = lastPoint?.equity ?? null
  const initialCapital = results.equity_curve[0]?.equity ?? equity

  return (
    <div className="metrics-grid animate-in">
      <div className="metric-card streaming-metric-card">
        <div className="metric-label">Running Backtest…</div>
        <div className="metric-value accent">{progress}%</div>
        <div className="progress-bar-track">
          <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Live Equity</div>
        <div className={`metric-value ${equity >= initialCapital ? 'positive' : 'negative'}`}>
          {equity !== null ? fmtINR(equity) : '—'}
        </div>
        <div className="metric-sub">{results.equity_curve.length} bars processed</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Trades So Far</div>
        <div className="metric-value accent">{results.trades.length}</div>
      </div>
      <div className="metric-card">
        <div className="metric-label">Ticker / Strategy</div>
        <div className="metric-value" style={{ fontSize: '1.15rem' }}>{results.ticker}</div>
        <div className="metric-sub">{results.strategy}</div>
      </div>
    </div>
  )
}

function OverallSummary({ results }) {
  const overallPnl = results.final_capital - results.initial_capital
  const isGain = overallPnl >= 0

  return (
    <div className={`overall-summary animate-in ${isGain ? 'overall-summary-gain' : 'overall-summary-loss'}`}>
      <div className="overall-summary-line">
        <span className="overall-summary-amount">{fmtINR(results.initial_capital)}</span>
        <span className="overall-summary-arrow">→</span>
        <span className="overall-summary-amount">{fmtINR(results.final_capital)}</span>
      </div>
      <div className={`overall-summary-delta ${isGain ? 'positive' : 'negative'}`}>
        {signedINR(overallPnl)} overall ({results.roi >= 0 ? '+' : ''}{results.roi}%)
      </div>
      <div className="overall-summary-note">
        Realized ({signedINR(results.realized_pnl)}) + unrealized ({signedINR(results.unrealized_pnl)}) on any open
        position, after {fmtINR(results.total_taxes)} in taxes already paid on closed trades.
      </div>
    </div>
  )
}

export default function MetricsGrid({ results, progress }) {
  if (!results) return null
  if (results.streaming) return <StreamingMetrics results={results} progress={progress} />

  const hasOpenPosition = results.open_position_value > 0

  const metrics = [
    {
      label: 'Net ROI',
      value: `${results.roi >= 0 ? '+' : ''}${results.roi}%`,
      className: results.roi >= 0 ? 'positive' : 'negative',
      sub: `${results.total_trades} trades executed`,
    },
    {
      label: 'Realized P&L',
      value: signedINR(results.realized_pnl),
      className: results.realized_pnl >= 0 ? 'positive' : 'negative',
      sub: `From closed trades · Win rate: ${results.win_rate}%`,
    },
    ...(hasOpenPosition ? [{
      label: 'Unrealized P&L',
      value: signedINR(results.unrealized_pnl),
      className: results.unrealized_pnl >= 0 ? 'positive' : 'negative',
      sub: 'Paper gain/loss on the open position',
    }] : []),
    {
      label: 'Taxes & Charges',
      value: fmtINR(results.total_taxes),
      className: 'negative',
      sub: 'STT + GST + Stamp + SEBI',
    },
    {
      label: 'Final Capital',
      value: fmtINR(results.final_capital),
      className: 'accent',
      sub: hasOpenPosition
        ? `Incl. ${fmtINR(results.open_position_value)} open position`
        : `Max Drawdown: ${results.max_drawdown}%`,
    },
  ]

  return (
    <>
      <OverallSummary results={results} />
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
    </>
  )
}
