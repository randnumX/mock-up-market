import { useState, useEffect } from 'react'
import { FileText, TriangleAlert, Play } from 'lucide-react'
import { useStrategies } from '../hooks/useBacktest'
import TickerCombobox from './TickerCombobox'
import PositionSizingControls from './PositionSizingControls'

export default function LiveSessionForm({ tickers, kiteConnected, onCreate, creating, error }) {
  const [ticker, setTicker] = useState('')
  const [strategy, setStrategy] = useState('macd')
  const [capital, setCapital] = useState(50000)
  const [mode, setMode] = useState('paper')
  const [maxCapitalPerTrade, setMaxCapitalPerTrade] = useState(10000)
  const [dailyLossLimit, setDailyLossLimit] = useState(2000)
  const [positionSizing, setPositionSizing] = useState({ mode: 'full' })
  const [confirmed, setConfirmed] = useState(false)
  const { strategies, fetchStrategies } = useStrategies()

  useEffect(() => { fetchStrategies() }, [fetchStrategies])

  const isLive = mode === 'live'

  const handleSubmit = async (e) => {
    e.preventDefault()
    const ok = await onCreate({
      ticker: ticker || tickers[0],
      strategy,
      capital: Number(capital),
      mode,
      max_capital_per_trade: maxCapitalPerTrade ? Number(maxCapitalPerTrade) : null,
      daily_loss_limit: dailyLossLimit ? Number(dailyLossLimit) : null,
      position_sizing: positionSizing.mode === 'full' ? undefined : positionSizing,
      confirm: isLive ? confirmed : undefined,
    })
    if (ok) setConfirmed(false)
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
          <label className="form-label">Ticker</label>
          <TickerCombobox tickers={tickers} value={ticker || tickers[0] || ''} onChange={setTicker} />
        </div>

        <div className="form-group">
          <label className="form-label">Strategy</label>
          <select className="form-select" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {strategies.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>

        <div className="form-group">
          <label className="form-label">Capital (₹)</label>
          <input type="number" className="form-input" value={capital} onChange={(e) => setCapital(e.target.value)} min="1000" step="1000" required />
        </div>

        <div className="form-group">
          <label className="form-label">Max Capital Per Trade (₹){isLive && ' — required'}</label>
          <input type="number" className="form-input" value={maxCapitalPerTrade} onChange={(e) => setMaxCapitalPerTrade(e.target.value)} min="100" step="500" required={isLive} />
          <p className="form-hint">Caps the size of any single order this session places, regardless of what the strategy requests.</p>
        </div>

        <div className="form-group">
          <label className="form-label">Daily Loss Limit (₹, optional)</label>
          <input type="number" className="form-input" value={dailyLossLimit} onChange={(e) => setDailyLossLimit(e.target.value)} min="0" step="500" />
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
