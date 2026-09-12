import { useEffect, useRef, useState } from 'react'
import { createChart, createSeriesMarkers, AreaSeries, ColorType } from 'lightweight-charts'
import { LineChart } from 'lucide-react'

export default function EquityChart({ results }) {
  const chartRef = useRef(null)
  const chartInstance = useRef(null)
  const [activeTab, setActiveTab] = useState('equity')

  useEffect(() => {
    if (!results || !chartRef.current) return

    // Destroy previous chart instance
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
      rightPriceScale: {
        borderColor: 'rgba(249,173,160,0.12)',
      },
      timeScale: {
        borderColor: 'rgba(249,173,160,0.12)',
        timeVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    })

    const curve = results.equity_curve || []

    // Parse dates
    const parseDate = (dateStr) => {
      const d = new Date(dateStr)
      if (isNaN(d.getTime())) return null
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    }

    if (activeTab === 'equity') {
      const data = curve
        .map((p) => ({ time: parseDate(p.time), value: p.equity }))
        .filter((p) => p.time !== null)

      const series = chart.addSeries(AreaSeries, {
        topColor: 'rgba(131, 182, 146, 0.35)',
        bottomColor: 'rgba(131, 182, 146, 0.0)',
        lineColor: '#83b692',
        lineWidth: 2,
      })
      series.setData(data)
    } else {
      const data = curve
        .map((p) => ({ time: parseDate(p.time), value: p.price }))
        .filter((p) => p.time !== null)

      const series = chart.addSeries(AreaSeries, {
        topColor: 'rgba(198, 91, 124, 0.3)',
        bottomColor: 'rgba(198, 91, 124, 0.0)',
        lineColor: '#c65b7c',
        lineWidth: 2,
      })
      series.setData(data)

      // Add trade markers
      const markers = (results.trades || [])
        .map((t) => {
          const time = parseDate(t.timestamp)
          if (!time) return null
          return {
            time,
            position: t.type === 'BUY' ? 'belowBar' : 'aboveBar',
            color: t.type === 'BUY' ? '#83b692' : '#f9627d',
            shape: t.type === 'BUY' ? 'arrowUp' : 'arrowDown',
            text: t.type,
          }
        })
        .filter(Boolean)
        .sort((a, b) => (a.time > b.time ? 1 : -1))

      if (markers.length > 0) {
        createSeriesMarkers(series, markers)
      }
    }

    chart.timeScale().fitContent()
    chartInstance.current = chart

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (chartRef.current) {
        chart.applyOptions({
          width: chartRef.current.clientWidth,
          height: chartRef.current.clientHeight,
        })
      }
    })
    resizeObserver.observe(chartRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartInstance.current = null
    }
  }, [results, activeTab])

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
