import { useEffect } from 'react'
import { usePositionSizingModes } from '../hooks/useBacktest'

/**
 * Shared by ConfigPanel (backtest) and LiveSessionForm (live trading) - both
 * need the same "how much to bet per trade" choice, backed by the same
 * /api/position-sizing-modes list so adding a new sizing mode server-side
 * shows up in both forms automatically.
 */
export default function PositionSizingControls({ value, onChange }) {
  const { modes, fetchModes } = usePositionSizingModes()

  useEffect(() => { fetchModes() }, [fetchModes])

  const mode = value.mode || 'full'
  const active = modes.find((m) => m.id === mode)

  const setMode = (newMode) => onChange({ mode: newMode })
  const setParam = (key, val) => onChange({ ...value, [key]: val })

  return (
    <div className="form-group">
      <label className="form-label">Position Sizing</label>
      <select className="form-select" value={mode} onChange={(e) => setMode(e.target.value)}>
        {modes.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
      </select>
      {active?.description && <p className="form-hint">{active.description}</p>}

      {mode === 'fixed_fraction' && (
        <div className="sizing-param-row">
          <label className="form-label">Fraction of Capital Per Trade</label>
          <input
            type="number"
            className="form-input"
            value={value.fraction ?? 0.2}
            onChange={(e) => setParam('fraction', Number(e.target.value))}
            min="0.01" max="1" step="0.05"
          />
        </div>
      )}

      {mode === 'volatility_target' && (
        <>
          <div className="sizing-param-row">
            <label className="form-label">Risk Per Trade (fraction of capital)</label>
            <input
              type="number"
              className="form-input"
              value={value.risk_per_trade ?? 0.01}
              onChange={(e) => setParam('risk_per_trade', Number(e.target.value))}
              min="0.001" max="0.5" step="0.005"
            />
          </div>
          <div className="sizing-param-row">
            <label className="form-label">Volatility Lookback (bars)</label>
            <input
              type="number"
              className="form-input"
              value={value.lookback ?? 14}
              onChange={(e) => setParam('lookback', Number(e.target.value))}
              min="2" max="100" step="1"
            />
          </div>
        </>
      )}
    </div>
  )
}
