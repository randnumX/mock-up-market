import { useEffect } from 'react'
import { useLive } from '../hooks/useLive'
import { useKite } from '../hooks/useBacktest'
import LiveSessionForm from './LiveSessionForm'
import LiveSessionsList from './LiveSessionsList'

const POLL_MS = 5000

export default function LiveTrading({ tickers }) {
  const { sessions, fetchSessions, marketOpen, fetchMarketStatus, createSession, creating, createError, stopSession, killAll } = useLive()
  const { status: kiteStatus, fetchStatus: fetchKiteStatus } = useKite()

  useEffect(() => {
    fetchSessions()
    fetchMarketStatus()
    fetchKiteStatus()
    const interval = setInterval(() => {
      fetchSessions()
      fetchMarketStatus()
    }, POLL_MS)
    return () => clearInterval(interval)
  }, [fetchSessions, fetchMarketStatus, fetchKiteStatus])

  return (
    <div>
      <div className="live-topbar animate-in">
        <div className="status-badge">
          <span className={`status-dot ${marketOpen ? 'online' : 'offline'}`} />
          <span>NSE {marketOpen === null ? '...' : marketOpen ? 'Open' : 'Closed'}</span>
        </div>
        <div className="status-badge">
          <span className={`status-dot ${kiteStatus.connected ? 'online' : 'offline'}`} />
          <span>Zerodha {kiteStatus.connected ? 'Connected' : 'Not Connected'}</span>
        </div>
      </div>

      <div className="main-grid">
        <div>
          <LiveSessionForm
            tickers={tickers}
            kiteConnected={kiteStatus.connected}
            onCreate={createSession}
            creating={creating}
            error={createError}
          />
        </div>
        <div className="right-panel">
          <LiveSessionsList sessions={sessions} onStop={stopSession} onKillAll={killAll} />
        </div>
      </div>
    </div>
  )
}
