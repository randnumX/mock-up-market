import { useState, useEffect } from 'react'
import { Copy, RefreshCw, Trophy, ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react'

export default function Movers({ tickers, tickerNames, onSelectTicker }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState(50)
  const [activeTab, setActiveTab] = useState('gainers') // gainers, losers, volume
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(null)

  const fetchMovers = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/movers?limit=${limit}`)
      if (!res.ok) throw new Error("Failed to fetch movers")
      const result = await res.json()
      setData(result)
    } catch (err) {
      setError("Failed to load market movers. Check connection.")
    }
    setLoading(false)
  }

  useEffect(() => {
    fetchMovers()
  }, [limit])

  const currentList = data ? (
    activeTab === 'gainers' ? data.top_gainers :
    activeTab === 'losers' ? data.top_losers :
    data.top_volume
  ) : []

  const handleCopy = () => {
    if (!currentList.length) return
    const csv = currentList.map(item => item.ticker).join(', ')
    navigator.clipboard.writeText(csv)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="animate-in" style={{ maxWidth: '900px', margin: '0 auto', paddingTop: '2rem' }}>
      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Trophy size={20} className="brand-icon" />
              Market Movers
            </div>
            <p className="form-hint" style={{ marginTop: '0.5rem' }}>
              View top performing and high-volume stocks from the last trading day.
              {data?.date && <span style={{ marginLeft: '0.5rem', color: 'var(--text-primary)' }}>Last data: {data.date}</span>}
            </p>
          </div>
          <button className="btn-secondary" onClick={fetchMovers} disabled={loading} style={{ padding: '0.5rem 1rem' }}>
            <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>

        <div style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', alignItems: 'center' }}>
          <div className="mode-toggle" style={{ flex: 1 }}>
            <button 
              className={`mode-btn ${activeTab === 'gainers' ? 'active' : ''}`} 
              onClick={() => setActiveTab('gainers')}
            >
              <ArrowUpRight size={14} style={{ color: 'var(--positive)' }} /> Top Gainers
            </button>
            <button 
              className={`mode-btn ${activeTab === 'losers' ? 'active' : ''}`} 
              onClick={() => setActiveTab('losers')}
            >
              <ArrowDownRight size={14} style={{ color: 'var(--negative)' }} /> Top Losers
            </button>
            <button 
              className={`mode-btn ${activeTab === 'volume' ? 'active' : ''}`} 
              onClick={() => setActiveTab('volume')}
            >
              <Activity size={14} style={{ color: 'var(--brand-blue)' }} /> Top Volume
            </button>
          </div>
          
          <select 
            className="form-select" 
            style={{ width: '150px' }}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value={10}>Top 10</option>
            <option value={50}>Top 50</option>
            <option value={100}>Top 100</option>
            <option value={200}>Top 200</option>
          </select>

          <button 
            className="btn-primary" 
            onClick={handleCopy} 
            disabled={!currentList.length}
            style={{ minWidth: '160px' }}
          >
            <Copy size={14} /> {copied ? "Copied!" : "Copy as CSV"}
          </button>
        </div>
      </div>

      {error ? (
        <div className="glass-card"><p className="kite-hint kite-error">{error}</p></div>
      ) : loading && !data ? (
        <div className="glass-card" style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
          <div className="spinner" />
        </div>
      ) : (
        <div className="glass-card" style={{ padding: '0' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Rank</th>
                <th style={{ padding: '1rem', fontWeight: 500 }}>Ticker</th>
                <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>Price (₹)</th>
                <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>% Change</th>
                <th style={{ padding: '1rem', fontWeight: 500, textAlign: 'right' }}>Volume</th>
              </tr>
            </thead>
            <tbody>
              {currentList.map((item, i) => {
                const isPositive = item.change_pct > 0;
                const isNegative = item.change_pct < 0;
                return (
                  <tr key={item.ticker} className="row-hover" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>{i + 1}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <button 
                        className="symbol-badge" 
                        onClick={() => onSelectTicker(item.ticker)}
                        title={tickerNames[item.ticker] || item.ticker}
                      >
                        {item.ticker}
                      </button>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                      {item.price.toFixed(2)}
                    </td>
                    <td style={{ 
                      padding: '0.75rem 1rem', 
                      textAlign: 'right', 
                      fontFamily: 'var(--font-mono)',
                      color: isPositive ? 'var(--positive)' : isNegative ? 'var(--negative)' : 'var(--text-primary)'
                    }}>
                      {isPositive ? '+' : ''}{item.change_pct.toFixed(2)}%
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      {item.volume.toLocaleString()}
                    </td>
                  </tr>
                )
              })}
              {currentList.length === 0 && (
                <tr>
                  <td colSpan="5" style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No data available. Have you synced the daily data?
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
