import { useState, useCallback, useRef } from 'react'

const API_BASE = '/api'

/**
 * Runs a backtest via Server-Sent Events (GET /api/backtest/stream) so the
 * equity curve renders bar-by-bar as it's computed, instead of popping in
 * all at once when a full response lands. `results` grows in place during
 * a run (`results.streaming === true`) and is replaced by the final,
 * authoritative result (identical shape to the plain POST /api/backtest
 * endpoint) once the "done" event arrives.
 */
export function useBacktest() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const esRef = useRef(null)

  const runBacktest = useCallback(({ ticker, capital, strategy, from_date, to_date }) => {
    esRef.current?.close()

    setLoading(true)
    setError(null)
    setProgress(0)
    setResults({ ticker, strategy, equity_curve: [], trades: [], streaming: true })

    const params = new URLSearchParams({ ticker, capital: String(Number(capital)), strategy })
    if (from_date) params.set('from_date', from_date)
    if (to_date) params.set('to_date', to_date)
    const es = new EventSource(`${API_BASE}/backtest/stream?${params}`)
    esRef.current = es

    es.onmessage = (msg) => {
      const event = JSON.parse(msg.data)

      if (event.type === 'tick') {
        setProgress(Math.round(((event.index + 1) / event.total) * 100))
        setResults((prev) => ({
          ...prev,
          equity_curve: [...(prev?.equity_curve || []), event.point],
          trades: event.new_trades.length ? [...(prev?.trades || []), ...event.new_trades] : prev?.trades || [],
        }))
      } else if (event.type === 'done') {
        setResults({ ...event.result, streaming: false })
        setProgress(100)
        setLoading(false)
        es.close()
      }
    }

    es.onerror = () => {
      setError('Lost connection to the backtest stream')
      setLoading(false)
      es.close()
    }
  }, [])

  return { results, loading, progress, error, runBacktest }
}

export function useTickers() {
  const [tickers, setTickers] = useState([])
  const [source, setSource] = useState('loading')

  const fetchTickers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tickers`)
      const data = await res.json()
      setTickers(data.tickers || [])
      setSource(data.source || 'unknown')
    } catch {
      setTickers(['SBIN', 'RELIANCE', 'HDFCBANK', 'INFY', 'TCS'])
      setSource('fallback')
    }
  }, [])

  return { tickers, source, fetchTickers }
}

export function useHealth() {
  const [health, setHealth] = useState(null)

  const fetchHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`)
      const data = await res.json()
      setHealth(data)
    } catch {
      setHealth({ status: 'error', db_connected: false, data_source: 'unavailable' })
    }
  }, [])

  return { health, fetchHealth }
}

export function useStrategies() {
  const [strategies, setStrategies] = useState([])

  const fetchStrategies = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/strategies`)
      const data = await res.json()
      setStrategies(data.strategies || [])
    } catch {
      setStrategies([{ id: 'macd', label: 'MACD Crossover (12/26/9)' }])
    }
  }, [])

  return { strategies, fetchStrategies }
}

export function useKite() {
  const [status, setStatus] = useState({ configured: false, connected: false })
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [syncError, setSyncError] = useState(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/kite/status`)
      const data = await res.json()
      setStatus(data)
    } catch {
      setStatus({ configured: false, connected: false })
    }
  }, [])

  const connect = useCallback(async () => {
    const res = await fetch(`${API_BASE}/kite/login-url`)
    const data = await res.json()
    if (data.login_url) {
      window.location.href = data.login_url
    }
  }, [])

  const disconnect = useCallback(async () => {
    await fetch(`${API_BASE}/kite/disconnect`, { method: 'POST' })
    await fetchStatus()
  }, [fetchStatus])

  const sync = useCallback(async (tickers) => {
    setSyncing(true)
    setSyncError(null)
    setSyncResult(null)
    try {
      const res = await fetch(`${API_BASE}/kite/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Sync failed')
      setSyncResult(data)
    } catch (err) {
      setSyncError(err.message)
    } finally {
      setSyncing(false)
    }
  }, [])

  return { status, fetchStatus, connect, disconnect, sync, syncing, syncResult, syncError }
}
