import { useState, useCallback } from 'react'

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

  return {
    sessions, fetchSessions,
    marketOpen, fetchMarketStatus,
    createSession, creating, createError,
    stopSession, killAll,
  }
}
