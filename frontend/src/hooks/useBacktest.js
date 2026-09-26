import { useState, useCallback, useRef, useEffect } from 'react'

const API_BASE = '/api'

/**
 * Runs a backtest via Server-Sent Events (GET /api/backtest/stream) so the
 * equity curve renders bar-by-bar as it's computed, instead of popping in
 * all at once when a full response lands. Each entry in `resultsList` grows
 * in place during a run (`status: 'streaming'`) and is replaced by the
 * final, authoritative result (identical shape to the plain POST
 * /api/backtest endpoint) once the "done" event arrives.
 *
 * Run history is authoritative on the server (MongoDB, via
 * GET/DELETE /api/backtest/runs) when available - the backend persists each
 * run's status as it streams and detects a mid-stream disconnect itself, so
 * a refresh/closed tab/restart no longer desyncs or loses a run's state.
 * Falls back to localStorage (this app's original behavior) only when
 * MongoDB isn't available, since backtesting itself has no MongoDB
 * dependency and should keep working zero-setup.
 */
export function useBacktest() {
  const [resultsList, setResultsList] = useState(() => {
    try {
      const saved = localStorage.getItem('backtest_results')
      if (saved) {
        const parsed = JSON.parse(saved)
        // If the user refreshed while streaming, mark it as interrupted
        return parsed.map(run => {
          if (run.status === 'streaming') {
            return { ...run, status: 'error', error: 'Run interrupted by page refresh.' }
          }
          return run
        })
      }
    } catch (e) {
      console.error('Failed to parse cached backtest results', e)
    }
    return []
  })
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  const dbAvailableRef = useRef(false)
  const esRef = useRef(null)

  // Only mirror to localStorage while running without MongoDB - once the
  // server is the source of truth, localStorage would just be a second,
  // increasingly stale copy nothing reads from again.
  useEffect(() => {
    if (dbAvailableRef.current) return
    localStorage.setItem('backtest_results', JSON.stringify(resultsList))
  }, [resultsList])

  const deleteRun = useCallback((id) => {
    setResultsList(prev => prev.filter(run => run.id !== id))
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/backtest/runs`)
        const data = await res.json()
        if (cancelled) return
        dbAvailableRef.current = !!data.db_available
        if (data.db_available) {
          setResultsList(data.runs || [])
          return
        }
      } catch (e) {
        console.error('Failed to fetch backtest run history from the server', e)
      }
      if (cancelled) return
      // No MongoDB (or the request failed) - fall back to localStorage.
      try {
        const saved = localStorage.getItem('backtest_results')
        if (!saved) return
        const parsed = JSON.parse(saved)
        // A 'streaming' entry only means anything while its EventSource is
        // alive in memory - that connection doesn't survive a page refresh,
        // so any entry still marked 'streaming' on load is a run that was
        // interrupted, not one still in progress.
        setResultsList(parsed.map(res => res.status === 'streaming'
          ? { ...res, status: 'error', errorMsg: 'Interrupted by page refresh' }
          : res))
      } catch (e) {
        console.error('Failed to parse cached backtest results', e)
      }
    })()
    return () => { cancelled = true }
  }, [])

  // Only mirror to localStorage while running without MongoDB - once the
  // server is the source of truth, localStorage would just be a second,
  // increasingly stale copy nothing reads from again.
  useEffect(() => {
    if (dbAvailableRef.current) return
    localStorage.setItem('backtest_results', JSON.stringify(resultsList))
  }, [resultsList])

  const refetchRuns = useCallback(async () => {
    if (!dbAvailableRef.current) return
    try {
      const res = await fetch(`${API_BASE}/backtest/runs`)
      const data = await res.json()
      setResultsList(data.runs || [])
    } catch (e) {
      console.error('Failed to refresh backtest run history', e)
    }
  }, [])

  const runBacktest = useCallback(async ({ tickers, capital, strategy, from_date, to_date, position_sizing, interval, max_capital_per_trade, daily_loss_limit }) => {
    esRef.current?.close()

    setLoading(true)
    setError(null)
    setProgress(0)

    // We send a single request for the entire portfolio
    const combinedTickers = tickers.join(',')
    const tempId = `pending-${Date.now()}` // swapped for the real DB id once the server assigns one

    const newEntry = {
      id: tempId,
      ticker: combinedTickers,
      strategy,
      equity_curve: [],
      trades: [],
      status: 'streaming',
      config: {
        capital: Number(capital),
        from_date: from_date || null,
        to_date: to_date || null,
        interval: interval || 'day',
        position_sizing: position_sizing || null,
        max_capital_per_trade: max_capital_per_trade || null,
        daily_loss_limit: daily_loss_limit || null,
      },
    }

    setResultsList(prev => [...prev, newEntry])

    await new Promise((resolve) => {
      const params = new URLSearchParams({ ticker: combinedTickers, capital: String(Number(capital)), strategy })
      if (interval) params.set('interval', interval)
      if (from_date) params.set('from_date', from_date)
      if (to_date) params.set('to_date', to_date)
      if (max_capital_per_trade) params.set('max_capital_per_trade', max_capital_per_trade)
      if (daily_loss_limit) params.set('daily_loss_limit', daily_loss_limit)
      if (position_sizing?.mode) {
        params.set('sizing_mode', position_sizing.mode)
        if (position_sizing.fraction !== undefined) params.set('sizing_fraction', position_sizing.fraction)
        if (position_sizing.risk_per_trade !== undefined) params.set('sizing_risk_per_trade', position_sizing.risk_per_trade)
        if (position_sizing.lookback !== undefined) params.set('sizing_lookback', position_sizing.lookback)
      }

      const es = new EventSource(`${API_BASE}/backtest/stream?${params}`)
      esRef.current = es
      let realId = tempId

      es.onmessage = (msg) => {
        const event = JSON.parse(msg.data)
        if (event.run_id) {
          realId = event.run_id
          es.runId = realId
        }

        if (event.type === 'tick') {
          setProgress(Math.round(((event.index + 1) / event.total) * 100))
          setResultsList(prev => prev.map(res => {
            if (res.id !== tempId && res.id !== realId) return res
            return {
              ...res,
              id: realId,
              equity_curve: [...res.equity_curve, event.point],
              trades: event.new_trades.length ? [...res.trades, ...event.new_trades] : res.trades,
            }
          }))
        } else if (event.type === 'done') {
          setResultsList(prev => prev.map(res => {
            if (res.id !== tempId && res.id !== realId) return res
            return { ...res, ...event.result, id: realId, status: 'done' }
          }))
          setProgress(100)
          es.close()
          resolve()
          refetchRuns() // reconcile with the DB-persisted, authoritative copy
        }
      }

      es.onerror = () => {
        setResultsList(prev => prev.map(res => {
          if (res.id !== tempId && res.id !== realId) return res
          return { ...res, id: realId, status: 'error', errorMsg: 'Stream failed' }
        }))
        es.close()
        resolve()
        // Give the backend's disconnect-cleanup a moment to persist the
        // interruption (it runs in a `finally` once the connection drops),
        // then pull the authoritative record instead of trusting our guess.
        setTimeout(refetchRuns, 800)
      }
    })

    setLoading(false)
  }, [refetchRuns])

  const fetchRunDetail = useCallback(async (id) => {
    if (!dbAvailableRef.current || String(id).startsWith('pending-')) return null
    try {
      const res = await fetch(`${API_BASE}/backtest/runs/${id}`)
      if (!res.ok) return null
      const full = await res.json()
      setResultsList(prev => prev.map(r => (r.id === id ? { ...r, ...full } : r)))
      return full
    } catch (e) {
      console.error('Failed to load backtest run detail', e)
      return null
    }
  }, [])

  const deleteResult = useCallback(async (id) => {
    setResultsList(prev => prev.filter(res => res.id !== id))
    if (dbAvailableRef.current && !String(id).startsWith('pending-')) {
      try {
        await fetch(`${API_BASE}/backtest/runs/${id}`, { method: 'DELETE' })
      } catch (e) {
        console.error('Failed to delete backtest run', e)
      }
    }
  }, [])

  const deleteResults = useCallback(async (ids) => {
    const idSet = new Set(ids)
    setResultsList(prev => prev.filter(res => !idSet.has(res.id)))
    if (dbAvailableRef.current) {
      await Promise.all(
        ids.filter(id => !String(id).startsWith('pending-')).map(id =>
          fetch(`${API_BASE}/backtest/runs/${id}`, { method: 'DELETE' }).catch(e => console.error('Failed to delete backtest run', e))
        )
      )
    }
  }, [])

  const clearArchivedResults = useCallback(() => {
    setResultsList(prev => {
      const archived = prev.filter(res => res.status === 'done' || res.status === 'error')
      if (dbAvailableRef.current) {
        Promise.all(
          archived.filter(res => !String(res.id).startsWith('pending-')).map(res =>
            fetch(`${API_BASE}/backtest/runs/${res.id}`, { method: 'DELETE' }).catch(e => console.error('Failed to delete backtest run', e))
          )
        )
      }
      return prev.filter(res => res.status === 'streaming' || res.status === 'pending')
    })
  }, [])

  // Poll for updates if any run is marked streaming but we don't have an active EventSource for it
  useEffect(() => {
    const hasOrphanedStream = resultsList.some(r => r.status === 'streaming' && r.id !== esRef.current?.runId);
    if (!hasOrphanedStream || !dbAvailableRef.current) return;

    const timer = setInterval(() => {
      refetchRuns();
    }, 2000);
    return () => clearInterval(timer);
  }, [resultsList, refetchRuns]);

  return { resultsList, loading, progress, error, runBacktest, fetchRunDetail, deleteResult, deleteResults, clearArchivedResults }
}

export function useTickers() {
  const [tickers, setTickers] = useState([])
  const [tickerNames, setTickerNames] = useState({})
  const [source, setSource] = useState('loading')

  const fetchTickers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/tickers`)
      const data = await res.json()
      setTickers(data.tickers || [])
      setTickerNames(data.names || {})
      setSource(data.source || 'unknown')
    } catch {
      setTickers(['SBIN', 'RELIANCE', 'HDFCBANK', 'INFY', 'TCS'])
      setTickerNames({
        'SBIN': 'State Bank of India',
        'RELIANCE': 'Reliance Industries',
        'HDFCBANK': 'HDFC Bank',
        'INFY': 'Infosys',
        'TCS': 'Tata Consultancy Services'
      })
      setSource('fallback')
    }
  }, [])

  return { tickers, tickerNames, source, fetchTickers }
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

export function useIntervals() {
  const [intervals, setIntervals] = useState([])

  const fetchIntervals = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/intervals`)
      const data = await res.json()
      setIntervals(data.intervals || [])
    } catch {
      setIntervals([{ id: 'day', label: 'Daily' }, { id: '5minute', label: '5 Minute' }, { id: '15minute', label: '15 Minute' }])
    }
  }, [])

  return { intervals, fetchIntervals }
}

export function usePositionSizingModes() {
  const [modes, setModes] = useState([])

  const fetchModes = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/position-sizing-modes`)
      const data = await res.json()
      setModes(data.modes || [])
    } catch {
      setModes([{ id: 'full', label: 'Full Capital' }])
    }
  }, [])

  return { modes, fetchModes }
}

export function useKite() {
  const [status, setStatus] = useState({ configured: false, connected: false })
  const [syncing, setSyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState(null)
  const [syncLogs, setSyncLogs] = useState([])
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
    setSyncProgress(null)
    setSyncLogs([])

    const es = new EventSource(`${API_BASE}/stream`)

    es.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data)
        if (event.type === 'sync_progress') {
          setSyncProgress({ current: event.current, total: event.total, ticker: event.ticker })
          setSyncLogs(prev => {
            const date = new Date().toLocaleTimeString('en-US', { hour12: false })
            const newLogs = [...prev, `[${date}] ✅ Processed ${event.ticker}`]
            return newLogs.length > 50 ? newLogs.slice(newLogs.length - 50) : newLogs
          })
        } else if (event.type === 'sync_complete') {
          setSyncResult(event.result)
          setSyncing(false)
          es.close()
        } else if (event.type === 'sync_error') {
          setSyncError(event.error)
          setSyncing(false)
          es.close()
        }
      } catch (err) { }
    }

    try {
      const res = await fetch(`${API_BASE}/kite/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.error || 'Sync failed')
      }
      // EventSource listener will flip syncing to false when done
    } catch (err) {
      setSyncError(err.message)
      setSyncing(false)
      es.close()
    }
  }, [])

  return { status, fetchStatus, connect, disconnect, sync, syncing, syncProgress, syncLogs, syncResult, syncError }
}
