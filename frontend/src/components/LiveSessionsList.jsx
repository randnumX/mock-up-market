import { useState } from 'react'
import { FileText, TriangleAlert, Square, Power, Zap } from 'lucide-react'

const STATUS_LABELS = {
  running: { label: 'Running', cls: 'online' },
  stopped: { label: 'Stopped', cls: 'offline' },
  halted: { label: 'Halted', cls: 'offline' },
}

function SessionCard({ session, onStop }) {
  const status = STATUS_LABELS[session.status] || STATUS_LABELS.stopped
  const positions = Object.entries(session.positions || {})
  const recentTrades = [...(session.history || [])].reverse().slice(0, 5)

  return (
    <div className="glass-card session-card animate-in">
      <div className="session-card-header">
        <div>
          <span className={`mode-pill ${session.mode === 'live' ? 'mode-pill-live' : 'mode-pill-paper'}`}>
            {session.mode === 'live' ? (<><TriangleAlert size={11} /> LIVE</>) : (<><FileText size={11} /> PAPER</>)}
          </span>
          <strong className="session-ticker">{session.ticker}</strong>
          <span className="session-strategy">{session.strategy}</span>
        </div>
        <div className="kite-status-row">
          <span className={`status-dot ${status.cls}`} />
          <span>{status.label}</span>
        </div>
      </div>

      <div className="session-metrics">
        <div>
          <div className="metric-label">Equity</div>
          <div className={`metric-value ${session.roi >= 0 ? 'positive' : 'negative'}`} style={{ fontSize: '1.15rem' }}>
            ₹{session.equity?.toLocaleString('en-IN')}
          </div>
        </div>
        <div>
          <div className="metric-label">ROI</div>
          <div className={`metric-value ${session.roi >= 0 ? 'positive' : 'negative'}`} style={{ fontSize: '1.15rem' }}>
            {session.roi >= 0 ? '+' : ''}{session.roi}%
          </div>
        </div>
        <div>
          <div className="metric-label">Ticks</div>
          <div className="metric-value accent" style={{ fontSize: '1.15rem' }}>{session.tick_count}</div>
        </div>
      </div>

      {session.halt_reason && <p className="kite-hint kite-error">{session.halt_reason}</p>}

      {positions.length > 0 && (
        <p className="form-hint">
          Holding {positions.map(([sym, p]) => `${p.qty} × ${sym}`).join(', ')} @ last price ₹{session.last_price}
        </p>
      )}

      {recentTrades.length > 0 && (
        <div className="trade-log-wrapper" style={{ maxHeight: 150, marginTop: '0.75rem' }}>
          <table className="trade-table">
            <tbody>
              {recentTrades.map((t, i) => (
                <tr key={i}>
                  <td><span className={`trade-type ${t.type === 'BUY' ? 'buy' : 'sell'}`}>{t.type}</span></td>
                  <td>{t.qty} @ ₹{t.price}</td>
                  <td className={t.pnl > 0 ? 'pnl-positive' : t.pnl < 0 ? 'pnl-negative' : ''}>
                    {t.pnl !== undefined ? `₹${t.pnl}` : t.error ? (<span className="pnl-negative"><TriangleAlert size={12} style={{ verticalAlign: 'text-bottom' }} /> {t.error}</span>) : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {session.status === 'running' && (
        <button className="btn-secondary btn-with-icon" style={{ marginTop: '0.75rem' }} onClick={() => onStop(session._id)}>
          <Square size={13} /> Stop Session
        </button>
      )}
    </div>
  )
}

export default function LiveSessionsList({ sessions, onStop, onKillAll }) {
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
        {sessions.map((s) => <SessionCard key={s._id} session={s} onStop={onStop} />)}
      </div>
    </div>
  )
}
