import { useState, useCallback } from 'react'

const API_BASE = '/api'

export function useBacktest() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runBacktest = useCallback(async ({ ticker, capital, strategy }) => {
    setLoading(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, capital: Number(capital), strategy }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || 'Backtest failed')
      }

      setResults(data)
    } catch (err) {
      setError(err.message)
      setResults(null)
    } finally {
      setLoading(false)
    }
  }, [])

  return { results, loading, error, runBacktest }
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
