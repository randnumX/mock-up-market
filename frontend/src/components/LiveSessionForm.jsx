import { useState, useEffect } from 'react'
import { FileText, TriangleAlert, Play } from 'lucide-react'
import { useStrategies } from '../hooks/useBacktest'
import PositionSizingControls from './PositionSizingControls'

export default function LiveSessionForm({ tickers, tickerNames, kiteConnected, onCreate, creating, error }) {
  const [strategy, setStrategy] = useState('')
  const [interval, setIntervalVal] = useState('')
  const [capital, setCapital] = useState(50000)
  const [mode, setMode] = useState('paper')
  const [maxCapitalPerTrade, setMaxCapitalPerTrade] = useState(10000)
  const [dailyLossLimit, setDailyLossLimit] = useState(2000)
  const [positionSizing, setPositionSizing] = useState({ mode: 'full' })
  const [confirmed, setConfirmed] = useState(false)
  const { strategies, fetchStrategies } = useStrategies()

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const isLive = mode === 'live'

  const [tickerInput, setTickerInput] = useState('')
  const [invalidTickers, setInvalidTickers] = useState([])

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    let inputs = []
    if (tickerInput.trim()) {
      inputs = tickerInput.split(',').map(t => t.trim().toUpperCase()).filter(t => t)
    }
    
    if (inputs.length === 0) {
      alert("Please enter at least one Ticker")
      setInvalidTickers([])
      return
    }
    
    const valid = []
    const invalid = []
    
    inputs.forEach(t => {
      if (tickers.includes(t)) {
        if (!valid.includes(t)) valid.push(t)
      } else {
        invalid.push(t)
      }
    })
    
    setInvalidTickers(invalid)
    
    if (valid.length === 0) {
      return
    }

    let allOk = true
    for (const t of valid) {
      const ok = await onCreate({
        ticker: t,
        strategy,
        interval,
        capital: Number(capital),
        mode,
        max_capital_per_trade: maxCapitalPerTrade ? Number(maxCapitalPerTrade) : null,
        daily_loss_limit: dailyLossLimit ? Number(dailyLossLimit) : null,
        position_sizing: positionSizing.mode === 'full' ? undefined : positionSizing,
        confirm: isLive ? confirmed : undefined,
      })
      if (!ok) {
        allOk = false
      }
    }
    
    if (allOk) {
      setConfirmed(false)
      if (tickerInput.trim()) {
        setTickerInput('')
      }
      setStrategy('')
      setIntervalVal('')
    }
  }

  return (
    <div className="glass-card animate-in">
      <div className="card-title">Start Live Session</div>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Mode</label>
          <div className="mode-toggle">
            <button type="button" className={`mode-btn ${mode === 'paper' ? 'active' : ''}`} onClick={() => setMode('paper')}>
              <FileText size={14} /> Paper (virtual money)
            </button>
            <button type="button" className={`mode-btn mode-btn-live ${mode === 'live' ? 'active' : ''}`} onClick={() => setMode('live')}>
              <TriangleAlert size={14} /> Live (real money)
            </button>
          </div>
        </div>

        {isLive && (
          <div className={`live-warning ${!kiteConnected ? 'live-warning-blocked' : ''}`}>
            {kiteConnected
              ? 'This will place REAL orders on your Zerodha account using real capital.'
              : 'Connect Zerodha (above) before you can start a live session.'}
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Tickers</label>
          <textarea 
            className="form-input" 
            placeholder="Paste comma-separated tickers (e.g. RELIANCE, INFY)" 
            value={tickerInput} 
            onChange={(e) => { setTickerInput(e.target.value); setInvalidTickers([]) }}
            rows={2}
            style={{ resize: 'none' }}
            required
          />
          {invalidTickers.length > 0 && (
            <div className="form-hint" style={{ color: 'var(--negative)', marginTop: '0.5rem' }}>
              Invalid tickers ignored: {invalidTickers.join(', ')}
            </div>
          )}
          <p className="form-hint" style={{ marginTop: '0.25rem' }}>
            A separate live session will be started for each valid ticker.
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Strategy</label>
          <select className="form-select" value={strategy} onChange={(e) => setStrategy(e.target.value)} required>
            <option value="" disabled>Select a Strategy</option>
            {strategies.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Timeframe (Interval)</label>
          <select
            className="form-select"
            value={interval}
            onChange={(e) => setIntervalVal(e.target.value)}
            required
          >
            <option value="" disabled>Select a Timeframe</option>
            <option value="day">Daily</option>
            <option value="5minute">5 Minute</option>
            <option value="15minute">15 Minute</option>
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Capital (₹)</label>
          <input type="number" className="form-input" value={capital} onChange={(e) => setCapital(e.target.value)} min="1000" step="1000" required />
        </div>

        <div className="form-group">
          <label className="form-label">Max Capital Per Trade (₹){isLive && ' — required'}</label>
          <input type="number" className="form-input" value={maxCapitalPerTrade} onChange={(e) => setMaxCapitalPerTrade(e.target.value)} min="100" step="any" required={isLive} />
          <p className="form-hint">Caps the size of any single order this session places, regardless of what the strategy requests.</p>
        </div>

        <div className="form-group">
          <label className="form-label">Daily Loss Limit (₹, optional)</label>
          <input type="number" className="form-input" value={dailyLossLimit} onChange={(e) => setDailyLossLimit(e.target.value)} min="0" step="any" />
          <p className="form-hint">Session auto-halts for the day once realized losses reach this amount.</p>
        </div>

        <PositionSizingControls value={positionSizing} onChange={setPositionSizing} />

        {isLive && (
          <label className="confirm-row">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} disabled={!kiteConnected} />
            I understand this places real orders with real money.
          </label>
        )}

        {error && <p className="kite-hint kite-error">{error}</p>}

        <button
          type="submit"
          className={`btn-primary ${isLive ? 'btn-danger' : ''}`}
          disabled={creating || (isLive && (!kiteConnected || !confirmed))}
        >
          {creating
            ? (<><div className="spinner" /> Starting…</>)
            : isLive
              ? (<><TriangleAlert size={16} /> Start Live Session</>)
              : (<><Play size={16} /> Start Paper Session</>)}
        </button>
      </form>
    </div>
  )
}
