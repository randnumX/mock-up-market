import { useEffect, useState } from 'react'
import { Play } from 'lucide-react'
import { useStrategies, useIntervals } from '../hooks/useBacktest'
import PositionSizingControls from './PositionSizingControls'
import TickerMultiSelect from './TickerMultiSelect'

const isoDate = (d) => d.toISOString().slice(0, 10)

const RANGE_PRESETS = [
  { label: '3M', days: 90 },
  { label: '6M', days: 182 },
  { label: '1Y', days: 365 },
  { label: 'All', days: null },
]

export default function ConfigPanel({ tickers, tickerNames, loading, onRun }) {
  const [capital, setCapital] = useState(100000)
  const [maxCapitalPerTrade, setMaxCapitalPerTrade] = useState('')
  const [dailyLossLimit, setDailyLossLimit] = useState('')
  const [selectedTickers, setSelectedTickers] = useState([])
  const [strategy, setStrategy] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [positionSizing, setPositionSizing] = useState({ mode: 'full' })
  const [interval, setIntervalVal] = useState('')
  const { strategies, fetchStrategies } = useStrategies()
  const { intervals, fetchIntervals } = useIntervals()

  useEffect(() => {
    fetchStrategies()
    fetchIntervals()
  }, [fetchStrategies, fetchIntervals])

  const applyPreset = (days) => {
    if (days === null) {
      setFromDate('')
      setToDate('')
      return
    }
    const to = new Date()
    const from = new Date()
    from.setDate(from.getDate() - days)
    setFromDate(isoDate(from))
    setToDate(isoDate(to))
  }

  const handleSubmit = (e) => {
    e.preventDefault()

    if (selectedTickers.length === 0) {
      alert("Please select at least one Ticker")
      return
    }

    onRun({
      tickers: selectedTickers,
      capital,
      strategy,
      interval,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      position_sizing: positionSizing.mode === 'full' ? undefined : positionSizing,
      max_capital_per_trade: maxCapitalPerTrade ? Number(maxCapitalPerTrade) : undefined,
      daily_loss_limit: dailyLossLimit ? Number(dailyLossLimit) : undefined,
    })
  }

  return (
    <div className="glass-card animate-in">
      <div className="card-title">Configure Backtest</div>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">Initial Capital (₹)</label>
          <input
            type="number"
            className="form-input"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            min="1000"
            step="1000"
            required
          />
        </div>

        <div className="form-group">
          <label className="form-label">Max Capital Per Trade (₹)</label>
          <input 
            type="number" 
            className="form-input" 
            value={maxCapitalPerTrade} 
            onChange={(e) => setMaxCapitalPerTrade(e.target.value)} 
            min="100" 
            step="any" 
          />
          <p className="form-hint">Caps the size of any single order, regardless of what the strategy requests. Leave blank for no cap.</p>
        </div>

        <div className="form-group">
          <label className="form-label">Daily Loss Limit (₹)</label>
          <input 
            type="number" 
            className="form-input" 
            value={dailyLossLimit} 
            onChange={(e) => setDailyLossLimit(e.target.value)} 
            min="0" 
            step="any" 
          />
          <p className="form-hint">Stops trading for the rest of the day if losses exceed this amount. Leave blank for no limit.</p>
        </div>

        <div className="form-group">
          <label className="form-label">Tickers</label>
          <TickerMultiSelect
            tickers={tickers}
            tickerNames={tickerNames}
            value={selectedTickers}
            onChange={setSelectedTickers}
            placeholder="Search a ticker or paste a comma-separated list..."
          />
          <p className="form-hint" style={{ marginTop: '0.25rem' }}>
            All selected tickers run together as one portfolio backtest, sharing a single capital pool.
          </p>
        </div>

        <div className="form-group">
          <label className="form-label">Strategy</label>
          <select
            className="form-select"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            required
          >
            <option value="" disabled>Select a Strategy</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id} title={s.description}>{s.label}</option>
            ))}
          </select>
          {strategies.find((s) => s.id === strategy)?.description && (
            <p className="form-hint">{strategies.find((s) => s.id === strategy).description}</p>
          )}
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
            {intervals.map((iv) => <option key={iv.id} value={iv.id}>{iv.label}</option>)}
          </select>
          {interval && interval !== 'day' && (
            <p className="form-hint kite-warning" style={{marginTop: '0.5rem'}}>Intraday backtesting is limited to the last 100 days of history due to Kite API limits.</p>
          )}
        </div>

        <div className="form-group">
          <label className="form-label">Date Range (optional)</label>
          <div className="date-range-presets">
            {RANGE_PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`preset-btn ${p.days === null ? (!fromDate && !toDate ? 'active' : '') : ''}`}
                onClick={() => applyPreset(p.days)}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="date-range-inputs">
            <input
              type="date"
              className="form-input"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              max={toDate || undefined}
            />
            <span className="date-range-sep">→</span>
            <input
              type="date"
              className="form-input"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              min={fromDate || undefined}
            />
          </div>
          <p className="form-hint">Leave blank to use all available history for the selected ticker.</p>
        </div>

        <PositionSizingControls value={positionSizing} onChange={setPositionSizing} />

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? (
            <>
              <div className="spinner" />
              Running...
            </>
          ) : (
            <><Play size={16} /> Run Backtest</>
          )}
        </button>
      </form>
    </div>
  )
}
