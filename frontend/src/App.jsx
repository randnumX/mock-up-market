import { useEffect, useState } from 'react'
import { BarChart3, Zap } from 'lucide-react'
import Header from './components/Header'
import StatusBadge from './components/StatusBadge'
import ConfigPanel from './components/ConfigPanel'
import KiteConnect from './components/KiteConnect'
import MetricsGrid from './components/MetricsGrid'
import EquityChart from './components/EquityChart'
import TradeLog from './components/TradeLog'
import LiveTrading from './components/LiveTrading'
import { useBacktest, useTickers, useHealth } from './hooks/useBacktest'

export default function App() {
  const [view, setView] = useState('backtest')
  const { results, loading, progress, error, runBacktest } = useBacktest()
  const { tickers, fetchTickers } = useTickers()
  const { health, fetchHealth } = useHealth()

  const refreshAfterSync = () => {
    fetchHealth()
    fetchTickers()
  }

  useEffect(() => {
    fetchHealth()
    fetchTickers()
  }, [fetchHealth, fetchTickers])

  return (
    <>
      <div className="app-bg" />
      <div className="app-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Header />
          <StatusBadge health={health} />
        </div>

        <div className="view-tabs animate-in">
          <button className={`view-tab ${view === 'backtest' ? 'active' : ''}`} onClick={() => setView('backtest')}>
            <BarChart3 size={15} /> Backtest
          </button>
          <button className={`view-tab ${view === 'live' ? 'active' : ''}`} onClick={() => setView('live')}>
            <Zap size={15} /> Live Trading
          </button>
        </div>

        {view === 'backtest' ? (
          <div className="main-grid">
            {/* Left Sidebar */}
            <div>
              <ConfigPanel
                tickers={tickers}
                loading={loading}
                onRun={runBacktest}
              />
              <div style={{ marginTop: '1rem' }}>
                <KiteConnect onSynced={refreshAfterSync} />
              </div>
              {error && (
                <div className="glass-card animate-in" style={{ marginTop: '1rem', borderColor: 'var(--negative)' }}>
                  <div className="card-title" style={{ color: 'var(--negative)' }}>Error</div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{error}</p>
                </div>
              )}
            </div>

            {/* Right Main Area */}
            <div className="right-panel">
              <MetricsGrid results={results} progress={progress} />
              <EquityChart results={results} />
              <TradeLog results={results} />
            </div>
          </div>
        ) : (
          <LiveTrading tickers={tickers} />
        )}
      </div>
    </>
  )
}
