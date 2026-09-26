import { useEffect, useState } from 'react'
import { BarChart3, Zap, Trophy, ArrowLeft, Trash2 } from 'lucide-react'
import Header from './components/Header'
import StatusBadge from './components/StatusBadge'
import ThemeToggle from './components/ThemeToggle'
import ConfigPanel from './components/ConfigPanel'
import KiteConnect from './components/KiteConnect'
import MetricsGrid from './components/MetricsGrid'
import EquityChart from './components/EquityChart'
import TradeLog from './components/TradeLog'
import LiveTrading from './components/LiveTrading'
import Scanner from './components/Scanner'
import Movers from './components/Movers'
import TickerModal from './components/TickerModal'
import ErrorBoundary from './components/ErrorBoundary'
import { useBacktest, useTickers, useHealth } from './hooks/useBacktest'

export default function App() {
  const [view, setView] = useState('backtest')
  const [selectedTicker, setSelectedTicker] = useState(null)
  const [selectedResultIndex, setSelectedResultIndex] = useState(null)
  const [drilldownTicker, setDrilldownTicker] = useState('ALL')
  const { resultsList, loading, progress, error, runBacktest, deleteResult, deleteResults, clearArchivedResults } = useBacktest()
  const { tickers, tickerNames, fetchTickers } = useTickers()
  const { health, fetchHealth } = useHealth()
  const [selectedRunIds, setSelectedRunIds] = useState(new Set())

  const refreshAfterSync = () => {
    fetchHealth()
    fetchTickers()
  }

  const handleRunBacktest = async (args) => {
    setSelectedResultIndex(null)
    await runBacktest(args)
  }

  useEffect(() => {
    fetchHealth()
    fetchTickers()
  }, [fetchHealth, fetchTickers])

  const archivedRunIds = resultsList.filter(res => res.status === 'done' || res.status === 'error').map(res => res.id)
  const allArchivedRunsSelected = archivedRunIds.length > 0 && archivedRunIds.every(id => selectedRunIds.has(id))

  return (
    <>
      <div className="app-bg" />
      <div className="app-container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Header />
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <StatusBadge health={health} />
            <ThemeToggle />
          </div>
        </div>

        <div className="view-tabs animate-in">
          <button className={`view-tab ${view === 'backtest' ? 'active' : ''}`} onClick={() => setView('backtest')}>
            <BarChart3 size={15} /> Backtest
          </button>
          <button className={`view-tab ${view === 'live' ? 'active' : ''}`} onClick={() => setView('live')}>
            <Zap size={15} /> Live Trading
          </button>
          <button className={`view-tab ${view === 'scanner' ? 'active' : ''}`} onClick={() => setView('scanner')}>
            <Zap size={15} /> Scanner
          </button>
          <button className={`view-tab ${view === 'movers' ? 'active' : ''}`} onClick={() => setView('movers')}>
            <Trophy size={15} /> Movers
          </button>
        </div>

        {view === 'backtest' ? (
          <div className="main-grid">
            {/* Left Sidebar */}
            <div>
              <ConfigPanel
                tickers={tickers}
                tickerNames={tickerNames}
                loading={loading}
                onRun={handleRunBacktest}
              />
              <div style={{ marginTop: '1rem' }}>
                <KiteConnect onSynced={refreshAfterSync} />
              </div>
              {error && (
                <div className="glass-card animate-in" style={{ marginTop: '1rem', borderColor: 'var(--negative)' }}>
                  <div className="card-title" style={{ color: 'var(--negative)' }}>Error</div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{error}</p>
                </div>
              )}
            </div>

            {/* Right Main Area */}
            <div className="right-panel">
              {resultsList && resultsList.length > 0 ? (
                selectedResultIndex !== null ? (
                  <div className="animate-in">
                    <button className="btn-secondary" onClick={() => setSelectedResultIndex(null)} style={{ marginBottom: '1rem', display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                      <ArrowLeft size={16} /> Back to Dashboard
                    </button>
                    <ErrorBoundary onReset={() => setSelectedResultIndex(null)}>
                    {(() => {
                      const res = resultsList[selectedResultIndex];
                      if (!res) {
                        return (
                          <div className="glass-card animate-in">
                            <div className="card-title">Run Not Found</div>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>This run no longer exists (it may have been deleted).</p>
                          </div>
                        )
                      }
                      const tickerStr = typeof res.ticker === 'string' ? res.ticker : ''
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <h2 style={{ margin: 0, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                              <span style={{ color: 'var(--brand-blue)', wordBreak: 'break-all' }}>
                                {tickerStr.length > 100 ? `${tickerStr.substring(0, 100)}... (${tickerStr.split(',').length} tickers)` : (tickerStr || 'Unknown')}
                              </span>
                              <span style={{ fontSize: '1rem', color: 'var(--text-muted)', fontWeight: 'normal', whiteSpace: 'nowrap' }}>— {res.strategy}</span>
                            </h2>
                            <div style={{ fontSize: '0.9rem' }}>
                              {res.status === 'pending' && <span style={{ color: 'var(--text-muted)' }}>Waiting...</span>}
                              {res.status === 'streaming' && (
                                <span style={{ color: 'var(--brand-blue)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                  <div className="spinner" style={{ width: '12px', height: '12px', borderWidth: '2px' }} /> Streaming ({progress}%)
                                </span>
                              )}
                              {res.status === 'error' && <span style={{ color: 'var(--negative)' }}>{res.errorMsg}</span>}
                              {res.status === 'done' && <span style={{ color: 'var(--positive)' }}>Complete</span>}
                            </div>
                          </div>

                          {res.config && (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1.5rem', fontSize: '0.82rem', color: 'var(--text-muted)', padding: '0.75rem 1rem', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                              <span>Capital: <strong style={{ color: 'var(--text-primary)' }}>₹{Number(res.config.capital).toLocaleString()}</strong></span>
                              <span>Interval: <strong style={{ color: 'var(--text-primary)' }}>{res.config.interval}</strong></span>
                              <span>Range: <strong style={{ color: 'var(--text-primary)' }}>{res.config.from_date || 'earliest'} → {res.config.to_date || 'latest'}</strong></span>
                              <span>Sizing: <strong style={{ color: 'var(--text-primary)' }}>{res.config.position_sizing?.mode || 'full'}</strong></span>
                              {res.config.max_capital_per_trade && (
                                <span>Max/Trade: <strong style={{ color: 'var(--text-primary)' }}>₹{Number(res.config.max_capital_per_trade).toLocaleString()}</strong></span>
                              )}
                              {res.config.daily_loss_limit && (
                                <span>Daily Loss Limit: <strong style={{ color: 'var(--text-primary)' }}>₹{Number(res.config.daily_loss_limit).toLocaleString()}</strong></span>
                              )}
                            </div>
                          )}

                          {res.status === 'error' && (
                            <div className="glass-card animate-in" style={{ borderColor: 'var(--negative)' }}>
                              <div className="card-title" style={{ color: 'var(--negative)' }}>Run Didn't Complete</div>
                              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: 0 }}>
                                {res.errorMsg || 'This run stopped before finishing.'}
                                {res.equity_curve?.length > 0 && ' Showing whatever data was captured before it stopped.'}
                              </p>
                            </div>
                          )}

                          {res.status !== 'pending' && (
                            <>
                              {res.ticker.split(',').length > 1 && (
                                <div style={{ marginTop: '1.5rem', marginBottom: '1.5rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                  <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginRight: '0.5rem' }}>Filter by Ticker:</span>
                                  <button
                                    onClick={() => setDrilldownTicker('ALL')}
                                    style={{
                                      padding: '0.35rem 0.75rem',
                                      fontSize: '0.85rem',
                                      borderRadius: '4px',
                                      border: drilldownTicker === 'ALL' ? '1px solid var(--brand-blue)' : '1px solid var(--border-color)',
                                      background: drilldownTicker === 'ALL' ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                                      color: drilldownTicker === 'ALL' ? 'var(--brand-blue)' : 'var(--text-primary)',
                                      cursor: 'pointer',
                                      transition: 'all 0.2s'
                                    }}
                                  >
                                    All Tickers (Portfolio)
                                  </button>
                                  {res.ticker.split(',').map(t => {
                                    const tick = t.trim()
                                    if (!tick) return null
                                    const isSelected = drilldownTicker === tick
                                    return (
                                      <button
                                        key={tick}
                                        onClick={() => setDrilldownTicker(tick)}
                                        style={{
                                          padding: '0.35rem 0.75rem',
                                          fontSize: '0.85rem',
                                          borderRadius: '4px',
                                          border: isSelected ? '1px solid var(--brand-blue)' : '1px solid var(--border-color)',
                                          background: isSelected ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                                          color: isSelected ? 'var(--brand-blue)' : 'var(--text-primary)',
                                          cursor: 'pointer',
                                          transition: 'all 0.2s'
                                        }}
                                      >
                                        {tick}
                                      </button>
                                    )
                                  })}
                                </div>
                              )}
                              
                              <MetricsGrid results={res} progress={res.status === 'streaming' ? progress : 100} drilldownTicker={drilldownTicker} />
                              <EquityChart results={res} drilldownTicker={drilldownTicker} />
                              <TradeLog results={res} drilldownTicker={drilldownTicker} />
                            </>
                          )}
                        </div>
                      )
                    })()}
                    </ErrorBoundary>
                  </div>
                ) : (
                  <div className="glass-card animate-in" style={{ padding: '0' }}>
                    <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div className="card-title" style={{ margin: 0 }}>Backtest Dashboard</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>{resultsList.length} total runs</div>
                        {archivedRunIds.length > 0 && (
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
                            onClick={() => setSelectedRunIds(allArchivedRunsSelected ? new Set() : new Set(archivedRunIds))}
                          >
                            {allArchivedRunsSelected ? 'Deselect All' : 'Select All'}
                          </button>
                        )}
                        {selectedRunIds.size > 0 ? (
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', borderColor: 'var(--negative)', color: 'var(--negative)' }}
                            onClick={() => {
                              if (window.confirm(`Delete ${selectedRunIds.size} selected run${selectedRunIds.size !== 1 ? 's' : ''}? This cannot be undone.`)) {
                                deleteResults([...selectedRunIds])
                                setSelectedRunIds(new Set())
                              }
                            }}
                          >
                            <Trash2 size={13} /> Delete Selected ({selectedRunIds.size})
                          </button>
                        ) : resultsList.some(res => res.status === 'done' || res.status === 'error') && (
                          <button
                            className="btn-secondary"
                            style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                            onClick={() => {
                              if (window.confirm('Delete all archived runs? This cannot be undone.')) clearArchivedResults()
                            }}
                          >
                            <Trash2 size={13} /> Clear Archived
                          </button>
                        )}
                      </div>
                    </div>
                    <div style={{ overflowX: 'auto' }}>
                          {/* Split runs into Active and Archived */}
                          {(() => {
                            const activeRuns = resultsList.map((res, idx) => ({ res, idx })).filter(({ res }) => res.status === 'streaming' || res.status === 'pending')
                            const archivedRuns = resultsList.map((res, idx) => ({ res, idx })).filter(({ res }) => res.status === 'done' || res.status === 'error').reverse()
                            
                            const allArchivedSelected = archivedRuns.length > 0 && archivedRuns.every(({ res }) => selectedRunIds.has(res.id))

                            const toggleSelectAllArchived = () => {
                              setSelectedRunIds(prev => {
                                if (allArchivedSelected) return new Set()
                                return new Set(archivedRuns.map(({ res }) => res.id))
                              })
                            }

                            const toggleSelectRun = (id) => {
                              setSelectedRunIds(prev => {
                                const next = new Set(prev)
                                if (next.has(id)) next.delete(id)
                                else next.add(id)
                                return next
                              })
                            }

                            const renderTable = (title, runs, isArchive = false) => {
                              if (runs.length === 0) return null;
                              return (
                                <div style={{ marginBottom: isArchive ? '0' : '2rem' }}>
                                  {isArchive && <div style={{ padding: '1rem 1.5rem', borderTop: '1px solid var(--border-color)', borderBottom: '1px solid var(--border-color)', backgroundColor: 'var(--bg-secondary)', fontWeight: 600, color: 'var(--text-primary)' }}>Archived Runs</div>}
                                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '600px' }}>
                                    <thead>
                                      <tr style={{ borderBottom: '1px solid var(--border-color)', color: 'var(--text-muted)' }}>
                                        {isArchive && (
                                          <th style={{ padding: '1rem 1.5rem', width: '40px' }}>
                                            <input type="checkbox" checked={allArchivedSelected} onChange={toggleSelectAllArchived} style={{ cursor: 'pointer' }} />
                                          </th>
                                        )}
                                        {isArchive && <th style={{ padding: '1rem 1.5rem', fontWeight: 500, width: '150px' }}>Run Date</th>}
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500 }}>Ticker</th>
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500 }}>Status</th>
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500, textAlign: 'right' }}>ROI</th>
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500, textAlign: 'right' }}>Win Rate</th>
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500, textAlign: 'right' }}>Max DD</th>
                                        <th style={{ padding: '1rem 1.5rem', fontWeight: 500, textAlign: 'right' }}>Final Capital</th>
                                        {isArchive && <th style={{ padding: '1rem 1.5rem', width: '60px' }} />}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {runs.map(({ res, idx }) => {
                                        const isStreaming = res.status === 'streaming'
                                        return (
                                          <tr key={idx} className="row-hover" style={{ borderBottom: '1px solid var(--border-color)', cursor: 'pointer' }} onClick={() => { setSelectedResultIndex(idx); setDrilldownTicker('ALL'); }}>
                                            {isArchive && (
                                              <td style={{ padding: '1rem 1.5rem' }} onClick={(e) => e.stopPropagation()}>
                                                <input
                                                  type="checkbox"
                                                  checked={selectedRunIds.has(res.id)}
                                                  onChange={() => toggleSelectRun(res.id)}
                                                  style={{ cursor: 'pointer' }}
                                                />
                                              </td>
                                            )}
                                            {isArchive && (
                                              <td style={{ padding: '1rem 1.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                                {(() => {
                                                  // created_at (ISO string) comes from DB-backed runs; a raw
                                                  // numeric res.id is the old localStorage-fallback timestamp.
                                                  const d = new Date(res.created_at || res.id)
                                                  return isNaN(d.getTime()) ? 'Unknown' : d.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })
                                                })()}
                                              </td>
                                            )}
                                            <td style={{ padding: '1rem 1.5rem', maxWidth: '300px' }}>
                                              <div style={{ fontWeight: 500, color: 'var(--brand-blue)', wordWrap: 'break-word', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }} title={res.ticker}>
                                                {res.ticker.length > 50 ? `${res.ticker.substring(0, 50)}...` : res.ticker}
                                              </div>
                                              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{res.strategy}</div>
                                            </td>
                                            <td style={{ padding: '1rem 1.5rem', fontSize: '0.9rem' }}>
                                              {res.status === 'pending' && <span style={{ color: 'var(--text-muted)' }}>Pending</span>}
                                              {isStreaming && <span style={{ color: 'var(--brand-blue)' }}>Running ({progress}%)</span>}
                                              {res.status === 'error' && <span style={{ color: 'var(--negative)' }}>Error</span>}
                                              {res.status === 'done' && <span style={{ color: 'var(--positive)' }}>Complete</span>}
                                            </td>
                                            <td style={{ padding: '1rem 1.5rem', textAlign: 'right', fontFamily: 'var(--font-mono)', color: res.roi > 0 ? 'var(--positive)' : res.roi < 0 ? 'var(--negative)' : 'var(--text-primary)' }}>
                                              {res.roi !== undefined ? `${res.roi > 0 ? '+' : ''}${res.roi}%` : isStreaming ? '...' : '-'}
                                            </td>
                                            <td style={{ padding: '1rem 1.5rem', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                                              {res.win_rate !== undefined ? `${res.win_rate}%` : isStreaming ? '...' : '-'}
                                            </td>
                                            <td style={{ padding: '1rem 1.5rem', textAlign: 'right', fontFamily: 'var(--font-mono)', color: 'var(--negative)' }}>
                                              {res.max_drawdown !== undefined ? `-${res.max_drawdown}%` : isStreaming ? '...' : '-'}
                                            </td>
                                            <td style={{ padding: '1rem 1.5rem', textAlign: 'right', fontFamily: 'var(--font-mono)' }}>
                                              {res.final_capital !== undefined ? `₹${res.final_capital.toLocaleString()}` : isStreaming ? '...' : '-'}
                                            </td>
                                            {isArchive && (
                                              <td style={{ padding: '1rem 1.5rem', textAlign: 'center' }}>
                                                <button
                                                  title="Delete this run"
                                                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'inline-flex' }}
                                                  onClick={(e) => {
                                                    e.stopPropagation()
                                                    if (window.confirm('Delete this archived run?')) {
                                                      deleteResult(res.id)
                                                      setSelectedRunIds(prev => {
                                                        if (!prev.has(res.id)) return prev
                                                        const next = new Set(prev)
                                                        next.delete(res.id)
                                                        return next
                                                      })
                                                    }
                                                  }}
                                                >
                                                  <Trash2 size={15} />
                                                </button>
                                              </td>
                                            )}
                                          </tr>
                                        )
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              )
                            }
                            
                            return (
                              <>
                                {renderTable('Active Backtests', activeRuns, false)}
                                {renderTable('Archived Runs', archivedRuns, true)}
                                {activeRuns.length === 0 && archivedRuns.length === 0 && (
                                  <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                                    No backtests run yet. Configure and run a backtest to see results.
                                  </div>
                                )}
                              </>
                            )
                          })()}
                    </div>
                  </div>
                )
              ) : (
                <div className="glass-card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <p className="form-hint" style={{ fontSize: '1.1rem' }}>Configure a backtest on the left and click Run to see results here.</p>
                </div>
              )}
            </div>
          </div>
        ) : view === 'live' ? (
          <LiveTrading tickers={tickers} tickerNames={tickerNames} onSelectTicker={setSelectedTicker} />
        ) : view === 'scanner' ? (
          <Scanner tickers={tickers} tickerNames={tickerNames} onSelectTicker={setSelectedTicker} />
        ) : (
          <Movers tickers={tickers} tickerNames={tickerNames} onSelectTicker={setSelectedTicker} />
        )}
      </div>
      
      {/* Global Ticker Modal */}
      <TickerModal symbol={selectedTicker} onClose={() => setSelectedTicker(null)} />
    </>
  )
}
