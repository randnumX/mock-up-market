import { useState } from 'react'
import { FileText, TriangleAlert, Square, Power, Zap, Trash2 } from 'lucide-react'
import { fmtINR, signedINR } from '../utils/format'
import EquityChart from './EquityChart'

const STATUS_LABELS = {
  running: { label: 'Running', cls: 'online' },
  stopped: { label: 'Stopped', cls: 'offline' },
  halted: { label: 'Halted', cls: 'offline' },
}

const filterChipStyle = (isSelected) => ({
  padding: '0.35rem 0.75rem',
  fontSize: '0.85rem',
  borderRadius: '4px',
  border: isSelected ? '1px solid var(--brand-blue)' : '1px solid var(--border-color)',
  background: isSelected ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
  color: isSelected ? 'var(--brand-blue)' : 'var(--text-primary)',
  cursor: 'pointer',
  transition: 'all 0.2s',
})

function SessionCard({ session, onStop, onDelete, onSelectTicker }) {
  const [drilldownTicker, setDrilldownTicker] = useState('ALL')
  const status = STATUS_LABELS[session.status] || STATUS_LABELS.stopped
  const tickers = session.tickers || (session.ticker ? [session.ticker] : [])
  const isPortfolio = tickers.length > 1
  const tickerStats = session.ticker_stats || {}
  const isDrilldown = drilldownTicker !== 'ALL'

  const allTrades = [...(session.history || [])].reverse()
  const trades = isDrilldown ? allTrades.filter((t) => t.symbol === drilldownTicker) : allTrades
  const recentTrades = trades.slice(0, 8)

  const capital = session.capital || 0
  const equity = session.equity ?? capital
  const overallPnl = equity - capital
  const isGain = overallPnl >= 0
  // A single ticker's "share" of a pooled capital account isn't a
  // meaningful number (same reason Backtest's per-ticker drilldown skips
  // ROI/equity too) - only realized/unrealized P&L are well-defined per ticker.
  const realizedPnl = isDrilldown ? (tickerStats[drilldownTicker]?.realized_pnl || 0) : (session.realized_pnl || 0)
  const unrealizedPnl = isDrilldown ? (tickerStats[drilldownTicker]?.unrealized_pnl || 0) : (session.unrealized_pnl || 0)

  return (
    <div className="glass-card session-card animate-in">
      <div className="session-card-header">
        <div>
          <span className={`mode-pill ${session.mode === 'live' ? 'mode-pill-live' : 'mode-pill-paper'}`}>
            {session.mode === 'live' ? (<><TriangleAlert size={11} /> LIVE</>) : (<><FileText size={11} /> PAPER</>)}
          </span>
          <span style={{ display: 'inline-flex', flexWrap: 'wrap', gap: '0.3rem', alignItems: 'center' }}>
            {tickers.map((t, i) => (
              <span key={t} style={{ display: 'inline-flex', alignItems: 'center' }}>
                <button
                  className="text-link session-ticker"
                  onClick={() => onSelectTicker?.(t)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  {t}
                </button>
                {i < tickers.length - 1 && <span style={{ color: 'var(--text-muted)' }}>,</span>}
              </span>
            ))}
          </span>
          <span className="session-strategy">{session.strategy}</span>
        </div>
        <div className="kite-status-row">
          <span className={`status-dot ${status.cls}`} />
          <span>{status.label}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1.5rem', fontSize: '0.82rem', color: 'var(--text-muted)', padding: '0.75rem 1rem', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)', margin: '0.75rem 0' }}>
        <span>Capital: <strong style={{ color: 'var(--text-primary)' }}>{fmtINR(session.capital)}</strong></span>
        <span>Interval: <strong style={{ color: 'var(--text-primary)' }}>{session.interval || 'day'}</strong></span>
        <span>Sizing: <strong style={{ color: 'var(--text-primary)' }}>{session.position_sizing?.mode || 'full'}</strong></span>
        {session.max_capital_per_trade && <span>Max/Trade: <strong style={{ color: 'var(--text-primary)' }}>{fmtINR(session.max_capital_per_trade)}</strong></span>}
        {session.daily_loss_limit && <span>Daily Loss Limit: <strong style={{ color: 'var(--text-primary)' }}>{fmtINR(session.daily_loss_limit)}</strong></span>}
      </div>

      {isPortfolio && (
        <div style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.4rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginRight: '0.25rem' }}>Filter:</span>
          <button style={filterChipStyle(!isDrilldown)} onClick={() => setDrilldownTicker('ALL')}>All Tickers (Portfolio)</button>
          {tickers.map((t) => (
            <button key={t} style={filterChipStyle(drilldownTicker === t)} onClick={() => setDrilldownTicker(t)}>{t}</button>
          ))}
        </div>
      )}

      {session.halt_reason && <p className="kite-hint kite-error">{session.halt_reason}</p>}

      {!isDrilldown ? (
        <>
          <div className={`overall-summary animate-in ${isGain ? 'overall-summary-gain' : 'overall-summary-loss'}`} style={{ margin: '0.75rem 0' }}>
            <div className="overall-summary-line">
              <span className="overall-summary-amount">{fmtINR(capital)}</span>
              <span className="overall-summary-arrow">→</span>
              <span className="overall-summary-amount">{fmtINR(equity)}</span>
            </div>
            <div className={`overall-summary-delta ${isGain ? 'positive' : 'negative'}`}>
              {signedINR(overallPnl)} overall ({session.roi >= 0 ? '+' : ''}{session.roi}%)
            </div>
            <div className="overall-summary-note">
              Realized ({signedINR(realizedPnl)}) + unrealized ({signedINR(unrealizedPnl)}) on any open position, after {fmtINR(session.total_taxes || 0)} in taxes already paid on closed trades.
            </div>
          </div>

          <div className="metrics-grid animate-in" style={{ marginBottom: '0.75rem' }}>
            <div className="metric-card">
              <div className="metric-label">Net ROI</div>
              <div className={`metric-value ${session.roi >= 0 ? 'positive' : 'negative'}`}>{session.roi >= 0 ? '+' : ''}{session.roi}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Realized P&L</div>
              <div className={`metric-value ${realizedPnl >= 0 ? 'positive' : 'negative'}`}>{signedINR(realizedPnl)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Unrealized P&L</div>
              <div className={`metric-value ${unrealizedPnl >= 0 ? 'positive' : 'negative'}`}>{signedINR(unrealizedPnl)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Taxes & Charges</div>
              <div className="metric-value negative">{fmtINR(session.total_taxes || 0)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Ticks</div>
              <div className="metric-value accent">{session.tick_count}</div>
            </div>
          </div>
        </>
      ) : (
        <div className="metrics-grid animate-in" style={{ marginBottom: '0.75rem' }}>
          <div className="metric-card">
            <div className="metric-label">Trades Executed</div>
            <div className="metric-value accent">{tickerStats[drilldownTicker]?.trades_count || 0}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Realized P&L</div>
            <div className={`metric-value ${realizedPnl >= 0 ? 'positive' : 'negative'}`}>{signedINR(realizedPnl)}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Win Rate</div>
            <div className="metric-value accent">{tickerStats[drilldownTicker]?.win_rate || 0}%</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Last Price</div>
            <div className="metric-value accent">{tickerStats[drilldownTicker]?.last_price != null ? fmtINR(tickerStats[drilldownTicker].last_price) : '—'}</div>
          </div>
        </div>
      )}

      <div style={{ marginBottom: '0.75rem' }}>
        <EquityChart results={session} drilldownTicker={drilldownTicker} />
      </div>

      {isPortfolio && !isDrilldown && (
        <div className="trade-log-wrapper" style={{ maxHeight: 150, marginBottom: '0.75rem' }}>
          <table className="trade-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Last Price</th>
                <th>Position</th>
                <th>Trades</th>
              </tr>
            </thead>
            <tbody>
              {tickers.map(t => {
                const stats = tickerStats[t] || {}
                return (
                  <tr key={t}>
                    <td>{t}</td>
                    <td>{stats.last_price != null ? fmtINR(stats.last_price) : '—'}</td>
                    <td>{stats.position_qty || 0}</td>
                    <td>{stats.trades_count || 0}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {recentTrades.length > 0 && (
        <div className="trade-log-wrapper" style={{ maxHeight: 150 }}>
          <table className="trade-table">
            <tbody>
              {recentTrades.map((t, i) => (
                <tr key={i}>
                  <td><span className={`trade-type ${t.type === 'BUY' ? 'buy' : 'sell'}`}>{t.type}</span></td>
                  {isPortfolio && !isDrilldown && <td style={{ fontWeight: 500 }}>{t.symbol}</td>}
                  <td>{t.qty} @ {fmtINR(t.price)}</td>
                  <td className={t.pnl > 0 ? 'pnl-positive' : t.pnl < 0 ? 'pnl-negative' : ''}>
                    {t.pnl !== undefined ? signedINR(t.pnl) : t.error ? (<span className="pnl-negative"><TriangleAlert size={12} style={{ verticalAlign: 'text-bottom' }} /> {t.error}</span>) : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
        {session.status === 'running' && (
          <button className="btn-secondary btn-with-icon" onClick={() => onStop(session._id)}>
            <Square size={13} /> Stop Session
          </button>
        )}
        {session.status !== 'running' && (
          <button
            className="btn-secondary btn-with-icon"
            onClick={() => {
              if (window.confirm('Delete this session? This cannot be undone.')) onDelete(session._id)
            }}
          >
            <Trash2 size={13} /> Delete
          </button>
        )}
      </div>
    </div>
  )
}

export default function LiveSessionsList({ sessions, onStop, onDelete, onKillAll, onSelectTicker }) {
  const [confirmingKill, setConfirmingKill] = useState(false)
  const runningCount = sessions.filter((s) => s.status === 'running').length

  const handleKillAll = () => {
    if (!confirmingKill) {
      setConfirmingKill(true)
      setTimeout(() => setConfirmingKill(false), 4000)
      return
    }
    setConfirmingKill(false)
    onKillAll()
  }

  if (sessions.length === 0) {
    return (
      <div className="glass-card">
        <div className="card-title">Live Sessions</div>
        <div className="empty-state">
          <div className="empty-state-icon"><Zap size={40} strokeWidth={1.5} /></div>
          <div className="empty-state-text">No live sessions yet. Start a paper session on the left to see it here.</div>
        </div>
      </div>
    )
  }

  return (
    <div>
      {runningCount > 0 && (
        <div className="kill-switch-bar animate-in">
          <span>{runningCount} session{runningCount !== 1 ? 's' : ''} running</span>
          <button className="btn-danger-outline btn-with-icon" onClick={handleKillAll}>
            {confirmingKill ? 'Click again to confirm — stops ALL sessions' : (<><Power size={14} /> Kill Switch: Stop All</>)}
          </button>
        </div>
      )}
      <div className="sessions-grid">
        {sessions.map((s) => <SessionCard key={s._id} session={s} onStop={onStop} onDelete={onDelete} onSelectTicker={onSelectTicker} />)}
      </div>
    </div>
  )
}
