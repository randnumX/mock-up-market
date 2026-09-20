import { useState, useEffect } from 'react'
import { Play, Square, Activity } from 'lucide-react'
import { fmtINR } from '../utils/format'
import { useLive } from '../hooks/useLive'
import TickerMultiSelect from './TickerMultiSelect'

export default function Scanner({ tickers, tickerNames, onSelectTicker }) {
  const [active, setActive] = useState(false)
  const [strategy, setStrategy] = useState('')
  const [watchlist, setWatchlist] = useState([])
  const [signals, setSignals] = useState({})
  const [intervalVal, setIntervalVal] = useState('')
  
  const { createSession } = useLive() // Reusing createSession from useLive to spawn a live trade!

  // Poll scanner state
  useEffect(() => {
    const fetchScanner = async () => {
      try {
        const res = await fetch('/api/scanner')
        const data = await res.json()
        setActive(data.active)
        if (data.active) {
          if (data.strategy) setStrategy(data.strategy)
          if (data.interval) setIntervalVal(data.interval)
          if (data.watchlist) {
            setWatchlist(data.watchlist)
          }
          setSignals(data.signals || {})
        } else {
          setSignals({})
        }
      } catch (err) {
        console.error("Failed to fetch scanner state", err)
      }
    }
    
    fetchScanner()
    const interval = setInterval(fetchScanner, 3000)
    return () => clearInterval(interval)
  }, [])

  const handleToggle = async () => {
    if (!active && (!strategy || !intervalVal || watchlist.length === 0)) {
      alert("Please select a Strategy, Timeframe, and Watchlist before starting.")
      return
    }
    const newActive = !active
    try {
      await fetch('/api/scanner', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          active: newActive,
          strategy: strategy,
          interval: intervalVal,
          watchlist: watchlist
        })
      })
      setActive(newActive)
      if (!newActive) setSignals({})
    } catch (err) {
      alert("Failed to toggle scanner")
    }
  }

  const handleLaunchTrade = async (ticker) => {
    const success = await createSession({
      ticker,
      mode: 'paper', // default to paper for safety from the scanner
      strategy,
      interval: intervalVal,
      capital: 100000
    })
    if (success) {
      alert(`Launched Paper Session for ${ticker}! Switch to Live Trading tab to view it.`)
    } else {
      alert("Failed to launch session.")
    }
  }

  return (
    <div className="animate-in">
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-title">Market Scanner</div>
        <p className="form-hint" style={{ marginBottom: '1.5rem' }}>
          Evaluate strategies across your entire watchlist simultaneously in real-time. 
          When a signal triggers, you can instantly spawn a live or paper trading session.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 2fr', gap: '1rem', marginBottom: '1.5rem' }}>
          <div>
            <label className="form-label">Strategy to Evaluate</label>
            <select 
              className="form-select" 
              value={strategy} 
              onChange={e => setStrategy(e.target.value)}
              disabled={active}
            >
              <option value="" disabled>Select a Strategy</option>
              <option value="MACDStrategy">MACD Crossover</option>
              <option value="SMACrossoverStrategy">SMA Crossover</option>
              <option value="RSIStrategy">RSI Mean Reversion</option>
              <option value="VWAPStrategy">VWAP Intraday</option>
              <option value="ORBStrategy">15-Min ORB (Breakout)</option>
              <option value="RSIScalpStrategy">RSI Scalper (5-Min)</option>
              <option value="EMAScalpStrategy">EMA Momentum (9/21)</option>
            </select>
          </div>
          <div>
            <label className="form-label">Timeframe (Interval)</label>
            <select 
              className="form-select" 
              value={intervalVal} 
              onChange={e => setIntervalVal(e.target.value)}
              disabled={active}
            >
              <option value="" disabled>Select a Timeframe</option>
              <option value="day">Daily</option>
              <option value="5minute">5 Minute</option>
              <option value="15minute">15 Minute</option>
            </select>
          </div>
          <div>
            <label className="form-label">Watchlist ({watchlist.length} Tickers)</label>
            <TickerMultiSelect
              tickers={tickers}
              tickerNames={tickerNames}
              value={watchlist}
              onChange={setWatchlist}
              placeholder="Search a ticker or paste a comma-separated list..."
              disabled={active}
              showBulkActions
            />
          </div>
        </div>

        <button 
          className={active ? "btn-danger-outline btn-with-icon" : "btn-primary btn-with-icon"}
          onClick={handleToggle}
        >
          {active ? <Square size={14} /> : <Play size={14} />}
          {active ? 'Stop Scanner' : 'Start Scanner'}
        </button>
      </div>

      <div className="glass-card">
        <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={18} /> Active Signals
        </div>
        
        {!active ? (
          <div className="empty-state">
            <div className="empty-state-text">Scanner is stopped. Click Start Scanner to begin evaluating.</div>
          </div>
        ) : Object.keys(signals).length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-text">Scanning {watchlist.length} tickers for {strategy} signals...</div>
          </div>
        ) : (
          <table className="trade-table" style={{ width: '100%', marginTop: '1rem' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', paddingBottom: '0.5rem' }}>Ticker</th>
                <th style={{ textAlign: 'left', paddingBottom: '0.5rem' }}>Signal</th>
                <th style={{ textAlign: 'right', paddingBottom: '0.5rem' }}>Trigger Price</th>
                <th style={{ textAlign: 'right', paddingBottom: '0.5rem' }}>Time</th>
                <th style={{ textAlign: 'right', paddingBottom: '0.5rem' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(signals).map(([ticker, sig]) => (
                <tr key={ticker} className="animate-in">
                  <td>
                    <button 
                      className="text-link" 
                      onClick={() => onSelectTicker(ticker)}
                      style={{ fontWeight: 'bold' }}
                    >
                      {ticker}
                    </button>
                  </td>
                  <td>
                    <span className={`trade-type ${sig.signal.toLowerCase()}`}>{sig.signal}</span>
                  </td>
                  <td style={{ textAlign: 'right' }}>{fmtINR(sig.price)}</td>
                  <td style={{ textAlign: 'right', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                    {new Date(sig.timestamp).toLocaleTimeString()}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button 
                      className="btn-secondary" 
                      style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
                      onClick={() => handleLaunchTrade(ticker)}
                    >
                      Trade Now
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
