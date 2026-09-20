import { useEffect, useRef, useState } from 'react'
import { createChart, createSeriesMarkers, AreaSeries, ColorType } from 'lightweight-charts'
import { LineChart } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'

const parseDate = (dateStr) => {
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return null
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// parseDate truncates full timestamps to a calendar day. Two source points
// with different times on the same day (e.g. mixed data providers storing
// "day" bars with different times-of-day) can collapse to the same display
// time - lightweight-charts requires strictly ascending, unique times, so
// collapse any repeats here, keeping the latest value for that day.
const dedupeByTime = (points) => {
  const out = []
  for (const p of points) {
    if (out.length > 0 && out[out.length - 1].time === p.time) {
      out[out.length - 1] = p
    } else {
      out.push(p)
    }
  }
  return out
}

// lightweight-charts takes literal colors, not CSS variables, so it can't
// just inherit the page's theme - these mirror index.css's two palettes
// and get picked by theme at chart-creation time (see the effect below).
const CHART_PALETTES = {
  dark: {
    text: '#d9c7c5',
    grid: 'rgba(247,214,208,0.06)',
    crosshair: 'rgba(226,180,189,0.5)',
    border: 'rgba(247,214,208,0.16)',
    equityTop: 'rgba(226, 180, 189, 0.3)',
    equityLine: '#e2b4bd',
    priceTop: 'rgba(247, 214, 208, 0.25)',
    priceLine: '#f7d6d0',
    buy: '#8fbe9d',
    sell: '#e0b968',
  },
  light: {
    text: '#7a7a7a',
    grid: 'rgba(74,74,74,0.06)',
    crosshair: 'rgba(226,180,189,0.6)',
    border: 'rgba(74,74,74,0.14)',
    equityTop: 'rgba(226, 180, 189, 0.35)',
    equityLine: '#c98d99',
    priceTop: 'rgba(74, 74, 74, 0.1)',
    priceLine: '#8a7570',
    buy: '#6b9080',
    sell: '#c9a227',
  },
}

const toMarker = (t, colors) => {
  const time = parseDate(t.timestamp)
  if (!time) return null
  return {
    time,
    position: t.type === 'BUY' ? 'belowBar' : 'aboveBar',
    color: t.type === 'BUY' ? colors.buy : colors.sell,
    shape: t.type === 'BUY' ? 'arrowUp' : 'arrowDown',
    text: t.type,
  }
}

export default function EquityChart({ results, drilldownTicker = 'ALL' }) {
  const chartRef = useRef(null)
  const chartInstance = useRef(null)
  const seriesInstance = useRef(null)
  const markersPlugin = useRef(null)
  const lastCurveLen = useRef(0)
  const lastChartTime = useRef(null)
  const colorsRef = useRef(CHART_PALETTES.dark)
  const [activeTab, setActiveTab] = useState('equity')
  const { theme } = useTheme()

  const isDrilldown = drilldownTicker !== 'ALL'
  const currentTab = isDrilldown ? 'price' : activeTab

  // (Re)build the chart when the tab, theme, or drilldownTicker changes
  useEffect(() => {
    if (!chartRef.current) return
    const colors = CHART_PALETTES[theme] || CHART_PALETTES.dark
    colorsRef.current = colors

    if (chartInstance.current) {
      chartInstance.current.remove()
      chartInstance.current = null
    }

    const chart = createChart(chartRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: colors.text,
        fontSize: 12,
        fontFamily: 'Inter, sans-serif',
      },
      grid: {
        vertLines: { color: colors.grid },
        horzLines: { color: colors.grid },
      },
      crosshair: {
        mode: 0,
        vertLine: { color: colors.crosshair, width: 1, style: 2 },
        horzLine: { color: colors.crosshair, width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border, timeVisible: false },
      handleScroll: true,
      handleScale: true,
    })

    const series = currentTab === 'equity'
      ? chart.addSeries(AreaSeries, {
        topColor: colors.equityTop,
        bottomColor: 'rgba(0, 0, 0, 0.0)',
        lineColor: colors.equityLine,
        lineWidth: 2,
      })
      : chart.addSeries(AreaSeries, {
        topColor: colors.priceTop,
        bottomColor: 'rgba(0, 0, 0, 0.0)',
        lineColor: colors.priceLine,
        lineWidth: 2,
      })

    const curve = isDrilldown 
      ? (results?.ticker_stats?.[drilldownTicker]?.prices || [])
      : (results?.equity_curve || [])
      
    const valueKey = currentTab === 'equity' ? 'equity' : 'price'
    const initialData = dedupeByTime(
      curve
        .map((p) => ({ time: parseDate(p.time), value: p[valueKey] }))
        .filter((p) => p.time !== null)
    )

    series.setData(initialData)
    lastCurveLen.current = curve.length
    lastChartTime.current = initialData.length > 0 ? initialData[initialData.length - 1].time : null

    markersPlugin.current = currentTab === 'price' ? createSeriesMarkers(series, []) : null
    if (markersPlugin.current) {
      const allTrades = results?.trades || []
      const trades = isDrilldown ? allTrades.filter(t => t.symbol === drilldownTicker) : allTrades
      const markers = trades.map((t) => toMarker(t, colors)).filter(Boolean).sort((a, b) => (a.time > b.time ? 1 : -1))
      markersPlugin.current.setMarkers(markers)
    }

    chart.timeScale().fitContent()
    chartInstance.current = chart
    seriesInstance.current = series

    return () => {
      chart.remove()
      chartInstance.current = null
      seriesInstance.current = null
      markersPlugin.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentTab, theme, drilldownTicker])

  // Append only what's new since the last render - keeps live streaming smooth
  useEffect(() => {
    if (!results || !seriesInstance.current) return

    const curve = isDrilldown 
      ? (results.ticker_stats?.[drilldownTicker]?.prices || [])
      : (results.equity_curve || [])
      
    const valueKey = currentTab === 'equity' ? 'equity' : 'price'

    if (curve.length < lastCurveLen.current) {
      seriesInstance.current.setData([])
      markersPlugin.current?.setMarkers([])
      lastCurveLen.current = 0
      lastChartTime.current = null
    }

    const newPoints = dedupeByTime(
      curve.slice(lastCurveLen.current)
        .map((p) => ({ time: parseDate(p.time), value: p[valueKey] }))
        .filter((p) => p.time !== null)
    )
    for (const p of newPoints) {
      // Skip a point that would go backwards relative to what's already on
      // the chart (possible right after the dedupe above merges what would
      // otherwise be two separate updates) - lightweight-charts only allows
      // updating the most recent bar or appending a later one.
      if (lastChartTime.current && p.time < lastChartTime.current) continue
      seriesInstance.current.update(p)
      lastChartTime.current = p.time
    }
    lastCurveLen.current = curve.length

    if (markersPlugin.current) {
      const allTrades = results.trades || []
      const trades = isDrilldown ? allTrades.filter(t => t.symbol === drilldownTicker) : allTrades
      const markers = trades.map((t) => toMarker(t, colorsRef.current)).filter(Boolean).sort((a, b) => (a.time > b.time ? 1 : -1))
      markersPlugin.current.setMarkers(markers)
    }

    chartInstance.current?.timeScale().fitContent()
    
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [results, drilldownTicker])

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
      <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          {isDrilldown ? `Price + Signals: ${drilldownTicker}` : (currentTab === 'equity' ? 'Portfolio Equity Curve' : 'Price Chart with Trade Signals')}
        </span>
        {(results.status === 'streaming' || results.status === 'running') && <span className="live-pill">● LIVE</span>}
      </div>
      
      {!isDrilldown && (
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
      )}
      
      <div className="chart-wrapper" ref={chartRef} style={{ marginTop: isDrilldown ? '1rem' : '0' }} />
    </div>
  )
}
