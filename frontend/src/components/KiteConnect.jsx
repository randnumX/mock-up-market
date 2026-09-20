import { useEffect, useRef } from 'react'
import { Link2, RefreshCw } from 'lucide-react'
import { useKite } from '../hooks/useBacktest'

export default function KiteConnect({ onSynced }) {
  const { status, fetchStatus, connect, disconnect, sync, syncing, syncProgress, syncLogs, syncResult, syncError } = useKite()
  const terminalRef = useRef(null)

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [syncLogs])

  useEffect(() => {
    fetchStatus()

    // After the OAuth redirect lands back on the app (?kite=connected|error)
    const params = new URLSearchParams(window.location.search)
    const kiteParam = params.get('kite')
    if (kiteParam) {
      fetchStatus()
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [fetchStatus])

  const handleSync = async () => {
    await sync()
    onSynced?.()
  }

  if (!status.configured) {
    return (
      <div className="glass-card animate-in kite-card">
        <div className="card-title">Real Market Data</div>
        <p className="kite-hint">
          Connect a Zerodha Kite Connect app to backtest against real NSE history
          instead of synthetic data. Add <code>KITE_API_KEY</code> / <code>KITE_API_SECRET</code> to
          backend/.env to enable this.
        </p>
      </div>
    )
  }

  return (
    <div className="glass-card animate-in kite-card">
      <div className="card-title">Real Market Data — Zerodha</div>

      <div className="kite-status-row">
        <span className={`status-dot ${status.connected ? 'online' : 'offline'}`} />
        <span>{status.connected ? `Connected${status.user_name ? ` as ${status.user_name}` : ''}` : 'Not connected'}</span>
      </div>

      {!status.connected ? (
        <button className="btn-primary" onClick={connect}><Link2 size={16} /> Connect Zerodha</button>
      ) : (
        <div className="kite-actions">
          <button className="btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? (
              <><div className="spinner" /> {syncProgress ? `Syncing ${syncProgress.current} / ${syncProgress.total}...` : 'Starting Sync...'}</>
            ) : (
              <><RefreshCw size={16} /> Sync Real Data</>
            )}
          </button>
          <button className="btn-secondary" onClick={disconnect} disabled={syncing}>Disconnect</button>
        </div>
      )}

      {/* Advanced Sync UI */}
      {syncing && syncProgress && (
        <div className="sync-dashboard animate-in">
          <div className="sync-progress-container">
            <div className="sync-progress-header">
              <span>Overall Progress</span>
              <span>{Math.round((syncProgress.current / syncProgress.total) * 100)}%</span>
            </div>
            <div className="sync-progress-bar-bg">
              <div 
                className="sync-progress-bar-fill" 
                style={{ width: `${(syncProgress.current / syncProgress.total) * 100}%` }} 
              />
            </div>
          </div>
          
          <div className="sync-terminal" ref={terminalRef}>
            {syncLogs.map((log, i) => (
              <div key={i} className="sync-terminal-line">{log}</div>
            ))}
            {syncLogs.length === 0 && <div className="sync-terminal-line" style={{color: 'var(--text-muted)'}}>Waiting for engine to start...</div>}
          </div>
        </div>
      )}

      {syncResult && !syncing && (
        <div className="animate-in" style={{ marginTop: '1rem' }}>
          <p className="kite-hint kite-success">
            ✅ Synced {syncResult.synced.length} tickers · {syncResult.total_candles} candles
            {syncResult.failed.length > 0 && ` · ${syncResult.failed.length} failed`}
          </p>
        </div>
      )}
      {syncError && !syncing && <p className="kite-hint kite-error" style={{ marginTop: '1rem' }}>❌ {syncError}</p>}
    </div>
  )
}
