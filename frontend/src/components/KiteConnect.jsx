import { useEffect } from 'react'
import { useKite } from '../hooks/useBacktest'

export default function KiteConnect({ onSynced }) {
  const { status, fetchStatus, connect, disconnect, sync, syncing, syncResult, syncError } = useKite()

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
        <button className="btn-primary" onClick={connect}>🔗 Connect Zerodha</button>
      ) : (
        <div className="kite-actions">
          <button className="btn-primary" onClick={handleSync} disabled={syncing}>
            {syncing ? (<><div className="spinner" /> Syncing…</>) : '⇅ Sync Real Data'}
          </button>
          <button className="btn-secondary" onClick={disconnect}>Disconnect</button>
        </div>
      )}

      {syncResult && (
        <p className="kite-hint kite-success">
          Synced {syncResult.synced.length} tickers · {syncResult.total_candles} candles
          {syncResult.failed.length > 0 && ` · ${syncResult.failed.length} failed`}
        </p>
      )}
      {syncError && <p className="kite-hint kite-error">{syncError}</p>}
    </div>
  )
}
