import { useState, useCallback, useEffect } from 'react'

const API_BASE = '/api'

export function useLive() {
  const [sessions, setSessions] = useState([])
  const [marketOpen, setMarketOpen] = useState(null)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState(null)

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/live/sessions`)
      const data = await res.json()
      setSessions(data.sessions || [])
    } catch {
      // keep last known sessions on transient network error
    }
  }, [])

  const fetchMarketStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/live/market-status`)
      const data = await res.json()
      setMarketOpen(data.is_open)
    } catch {
      setMarketOpen(null)
    }
  }, [])

  const createSession = useCallback(async (payload) => {
    setCreating(true)
    setCreateError(null)
    try {
      const res = await fetch(`${API_BASE}/live/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error || 'Failed to start session')
      await fetchSessions()
      return true
    } catch (err) {
      setCreateError(err.message)
      return false
    } finally {
      setCreating(false)
    }
  }, [fetchSessions])

  const stopSession = useCallback(async (sessionId) => {
    await fetch(`${API_BASE}/live/sessions/${sessionId}/stop`, { method: 'POST' })
    await fetchSessions()
  }, [fetchSessions])

  const killAll = useCallback(async () => {
    await fetch(`${API_BASE}/live/kill-all`, { method: 'POST' })
    await fetchSessions()
  }, [fetchSessions])

  const deleteSession = useCallback(async (sessionId) => {
    const res = await fetch(`${API_BASE}/live/sessions/${sessionId}`, { method: 'DELETE' })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Failed to delete session')
    await fetchSessions()
  }, [fetchSessions])

  // Subscribe to real-time WebSocket ticks via Server-Sent Events
  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE}/stream`)
    
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setSessions(prev => prev.map(s => {
          if (s.ticker === data.symbol && s.status === 'running') {
            const positions = Object.values(s.positions || {})
            const open_value = positions.reduce((sum, pos) => sum + (pos.qty * data.price), 0)
            const open_cost = positions.reduce((sum, pos) => sum + (pos.qty * pos.avg_price), 0)
            const equity = (s.cash || 0) + open_value
            const roi = s.capital ? ((equity - s.capital) / s.capital * 100) : 0
            
            return {
              ...s,
              last_price: data.price,
              open_position_value: open_value,
              unrealized_pnl: open_value - open_cost,
              equity: equity,
              roi: roi
            }
          }
          return s
        }))
      } catch (err) {
        // ignore parse errors (e.g. ping events)
      }
    }
    
    return () => eventSource.close()
  }, [])

  return {
    sessions, fetchSessions,
    marketOpen, fetchMarketStatus,
    createSession, creating, createError,
    stopSession, killAll, deleteSession,
  }
}
