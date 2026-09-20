import { useEffect, useRef, useState } from 'react'
import { createChart } from 'lightweight-charts'
import { useTheme } from '../hooks/useTheme'

export default function AssetChart({ symbol }) {
  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef(null)
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const { theme } = useTheme()

  useEffect(() => {
    let active = true
    const fetchData = async () => {
      setLoading(true)
      try {
        const res = await fetch(`/api/tickers/${symbol}/history`)
        const json = await res.json()
        if (active && json.history) {
          setData(json.history)
        }
      } catch (err) {
        console.error("Failed to fetch ticker history", err)
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchData()
    return () => { active = false }
  }, [symbol])

  useEffect(() => {
    if (!chartContainerRef.current) return
    
    // We want the chart to render even if empty to show the grid
    const chartOptions = {
      autoSize: true,
      layout: {
        background: { type: 'solid', color: 'transparent' },
        textColor: theme === 'dark' ? '#d9c7c5' : '#7a7a7a',
        fontFamily: 'Inter, sans-serif'
      },
      grid: {
        vertLines: { color: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(74, 74, 74, 0.08)' },
        horzLines: { color: theme === 'dark' ? 'rgba(255, 255, 255, 0.05)' : 'rgba(74, 74, 74, 0.08)' },
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        fixLeftEdge: true,
      },
      handleScroll: true,
      handleScale: true,
    }

    const chart = createChart(chartContainerRef.current, chartOptions)
    chartRef.current = chart

    const series = chart.addAreaSeries({
      lineColor: theme === 'dark' ? '#e2b4bd' : '#b85c62',
      topColor: theme === 'dark' ? 'rgba(226, 180, 189, 0.4)' : 'rgba(184, 92, 98, 0.4)',
      bottomColor: theme === 'dark' ? 'rgba(226, 180, 189, 0.0)' : 'rgba(184, 92, 98, 0.0)',
      lineWidth: 2,
    })
    seriesRef.current = series

    return () => {
      chart.remove()
    }
  }, [theme])

  useEffect(() => {
    if (seriesRef.current && data.length > 0) {
      // Lightweight charts requires strictly ascending unique times.
      // We map the incoming data to extract just `time` and `value`.
      const uniqueData = []
      const seenTimes = new Set()
      
      for (const row of data) {
        // row.time is YYYY-MM-DD
        if (!seenTimes.has(row.time)) {
          seenTimes.add(row.time)
          uniqueData.push({ time: row.time, value: row.value })
        }
      }
      
      uniqueData.sort((a, b) => a.time.localeCompare(b.time))
      seriesRef.current.setData(uniqueData)
      chartRef.current.timeScale().fitContent()
    }
  }, [data])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
          <div className="spinner" />
        </div>
      )}
      {!loading && data.length === 0 && (
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10, color: 'var(--text-muted)' }}>
          No historical data found for {symbol}
        </div>
      )}
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  )
}
