import { useEffect, useRef, useState } from 'react'
import { createChart, createSeriesMarkers, AreaSeries, ColorType } from 'lightweight-charts'
import { LineChart } from 'lucide-react'

const parseDate = (dateStr) => {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const toMarker = (t) => {
  const time = parseDate(t.timestamp)
  if (!time) return null
  return {
    time,
    position: t.type === 'BUY' ? 'belowBar' : 'aboveBar',
    color: t.type === 'BUY' ? '#83b692' : '#f9627d',
    shape: t.type === 'BUY' ? 'arrowUp' : 'arrowDown',
    text: t.type,
  }
}

export default function EquityChart({ results }) {
  const chartRef = useRef(null)
  const chartInstance = useRef(null)
  const seriesInstance = useRef(null)
  const markersPlugin = useRef(null)
  const lastCurveLen = useRef(0)
  const [activeTab, setActiveTab] = useState('equity')

  // (Re)build the chart when the tab changes, or on mount - hydrated with
  // whatever data is already available so switching tabs mid-stream works.
  useEffect(() => {
    if (!chartRef.current) return

    if (chartInstance.current) {
      chartInstance.current.remove()
      chartInstance.current = null
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#c65b7c',
        fontSize: 12,
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { color: 'rgba(249,173,160,0.05)' },
        horzLines: { color: 'rgba(249,173,160,0.05)' },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: 'rgba(131,182,146,0.4)', width: 1, style: 2 },
        horzLine: { color: 'rgba(131,182,146,0.4)', width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: 'rgba(249,173,160,0.12)' },
      timeScale: { borderColor: 'rgba(249,173,160,0.12)', timeVisible: false },
      handleScroll: true,
      handleScale: true,
    })

    const series = activeTab === 'equity'
      ? chart.addSeries(AreaSeries, {
        topColor: 'rgba(131, 182, 146, 0.35)',
        bottomColor: 'rgba(131, 182, 146, 0.0)',
        lineColor: '#83b692',
        lineWidth: 2,
      })
      : chart.addSeries(AreaSeries, {
        topColor: 'rgba(198, 91, 124, 0.3)',
        bottomColor: 'rgba(198, 91, 124, 0.0)',
        lineColor: '#c65b7c',
        lineWidth: 2,
      })

    const curve = results?.equity_curve || []
    const valueKey = activeTab === 'equity' ? 'equity' : 'price'
    const initialData = curve
      .map((p) => ({ time: parseDate(p.time), value: p[valueKey] }))
      .filter((p) => p.time !== null)
    series.setData(initialData)
    lastCurveLen.current = curve.length

    markersPlugin.current = activeTab === 'price' ? createSeriesMarkers(series, []) : null
    if (markersPlugin.current) {
      const markers = (results?.trades || []).map(toMarker).filter(Boolean).sort((a, b) => (a.time > b.time ? 1 : -1))
      markersPlugin.current.setMarkers(markers)
    }

    chart.timeScale().fitContent()
    chartInstance.current = chart
    seriesInstance.current = series

    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth, height: chartRef.current.clientHeight })
      }
    })
    resizeObserver.observe(chartRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartInstance.current = null
      seriesInstance.current = null
      markersPlugin.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  // Append only what's new since the last render - keeps live streaming
  // smooth (no chart teardown/rebuild per tick) instead of full setData().
  useEffect(() => {
    if (!results || !seriesInstance.current) return

    const curve = results.equity_curve || []
    const valueKey = activeTab === 'equity' ? 'equity' : 'price'

    if (curve.length < lastCurveLen.current) {
      // A new run started (curve reset to empty/shorter) - clear and restart.
      seriesInstance.current.setData([])
      markersPlugin.current?.setMarkers([])
      lastCurveLen.current = 0
    }

    const newPoints = curve.slice(lastCurveLen.current)
    for (const p of newPoints) {
      const time = parseDate(p.time)
      if (time) seriesInstance.current.update({ time, value: p[valueKey] })
    }
    lastCurveLen.current = curve.length

    if (markersPlugin.current) {
      const markers = (results.trades || []).map(toMarker).filter(Boolean).sort((a, b) => (a.time > b.time ? 1 : -1))
      markersPlugin.current.setMarkers(markers)
    }

    if (!results.streaming) {
      chartInstance.current?.timeScale().fitContent()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results])

  if (!results) {
    return (
      <div className="glass-card">
        <div className="card-title">Chart</div>
        <div className="empty-state">
          <div className="empty-state-icon"><LineChart size={40} strokeWidth={1.5} /></div>
          <div className="empty-state-text">
            Configure your backtest parameters and hit <strong>Run Backtest</strong> to see the equity curve here.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="glass-card animate-in">
      <div className="card-title">
        {activeTab === 'equity' ? 'Portfolio Equity Curve' : 'Price Chart with Trade Signals'}
        {results.streaming && <span className="live-pill">● LIVE</span>}
      </div>
      <div className="chart-tabs">
        <button
          className={`chart-tab ${activeTab === 'equity' ? 'active' : ''}`}
          onClick={() => setActiveTab('equity')}
        >
          Equity Curve
        </button>
        <button
          className={`chart-tab ${activeTab === 'price' ? 'active' : ''}`}
          onClick={() => setActiveTab('price')}
        >
          Price + Signals
        </button>
      </div>
      <div className="chart-wrapper" ref={chartRef} />
    </div>
  )
}
