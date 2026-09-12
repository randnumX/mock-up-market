import { useEffect, useState } from 'react'
import { Play } from 'lucide-react'
import { useStrategies } from '../hooks/useBacktest'
import TickerCombobox from './TickerCombobox'
import PositionSizingControls from './PositionSizingControls'

const isoDate = (d) => d.toISOString().slice(0, 10)

const RANGE_PRESETS = [
  { label: '3M', days: 90 },
  { label: '6M', days: 182 },
  { label: '1Y', days: 365 },
  { label: 'All', days: null },
]

export default function ConfigPanel({ tickers, loading, onRun }) {
  const [capital, setCapital] = useState(100000)
  const [ticker, setTicker] = useState('')
  const [strategy, setStrategy] = useState('macd')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [positionSizing, setPositionSizing] = useState({ mode: 'full' })
  const { strategies, fetchStrategies } = useStrategies()

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

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
    onRun({
      ticker: ticker || tickers[0],
      capital,
      strategy,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      position_sizing: positionSizing.mode === 'full' ? undefined : positionSizing,
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
          <label className="form-label">Ticker</label>
          <TickerCombobox
            tickers={tickers}
            value={ticker || tickers[0] || ''}
            onChange={setTicker}
          />
        </div>

        <div className="form-group">
          <label className="form-label">Strategy</label>
          <select
            className="form-select"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            {strategies.map((s) => (
              <option key={s.id} value={s.id} title={s.description}>{s.label}</option>
            ))}
          </select>
          {strategies.find((s) => s.id === strategy)?.description && (
            <p className="form-hint">{strategies.find((s) => s.id === strategy).description}</p>
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
