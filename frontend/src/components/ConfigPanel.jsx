import { useEffect, useState } from 'react'
import { useStrategies } from '../hooks/useBacktest'

export default function ConfigPanel({ tickers, loading, onRun }) {
  const [capital, setCapital] = useState(100000)
  const [ticker, setTicker] = useState('')
  const [strategy, setStrategy] = useState('macd')
  const { strategies, fetchStrategies } = useStrategies()

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

  const handleSubmit = (e) => {
    e.preventDefault()
    onRun({ ticker: ticker || tickers[0], capital, strategy })
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
          <select
            className="form-select"
            value={ticker || tickers[0] || ''}
            onChange={(e) => setTicker(e.target.value)}
            required
          >
            {tickers.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
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

        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? (
            <>
              <div className="spinner" />
              Running...
            </>
          ) : (
            '▶ Run Backtest'
          )}
        </button>
      </form>
    </div>
  )
}
