import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'

const MAX_RESULTS = 50

/**
 * Type-to-filter ticker picker. A plain <select> stops being usable once
 * Mongo has thousands of real BSE tickers loaded - this keeps the same
 * "pick one ticker" contract but scales to that list size.
 */
export default function TickerCombobox({ tickers, tickerNames, value, onChange, id }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const containerRef = useRef(null)
  const inputRef = useRef(null)

  const isQueryJustValue = query === value
  const filtered = (query && !isQueryJustValue
    ? tickers.filter((t) => {
        const q = query.toLowerCase()
        const name = (tickerNames?.[t] || '').toLowerCase()
        return t.toLowerCase().includes(q) || name.includes(q)
      })
    : tickers
  ).slice(0, MAX_RESULTS)

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const select = (ticker) => {
    onChange(ticker)
    setQuery(ticker)
    setOpen(false)
    inputRef.current?.blur()
  }

  const handleKeyDown = (e) => {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      setOpen(true)
      return
    }
    if (!open) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[highlighted]) select(filtered[highlighted])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="ticker-combobox" ref={containerRef}>
      <div className="ticker-combobox-input-wrap">
        <input
          id={id}
          ref={inputRef}
          type="text"
          className="form-input"
          placeholder="Search ticker..."
          value={open ? query : (value || '')}
          onFocus={(e) => {
            setQuery(value || '')
            setOpen(true)
            setHighlighted(0)
            e.target.select()
          }}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setHighlighted(0) }}
          onKeyDown={handleKeyDown}
          autoComplete="off"
        />
        <ChevronDown size={14} className="ticker-combobox-chevron" />
      </div>

      {open && (
        <ul className="ticker-combobox-list">
          {filtered.length === 0 && <li className="ticker-combobox-empty">No matching tickers</li>}
          {filtered.map((t, i) => (
            <li
              key={t}
              className={`ticker-combobox-option ${t === value ? 'selected' : ''} ${i === highlighted ? 'highlighted' : ''}`}
              onMouseDown={() => select(t)}
              onMouseEnter={() => setHighlighted(i)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{t}</span>
                {tickerNames?.[t] && (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85em', marginLeft: '0.5rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {tickerNames[t]}
                  </span>
                )}
              </div>
            </li>
          ))}
          {tickers.length > MAX_RESULTS && filtered.length === MAX_RESULTS && (
            <li className="ticker-combobox-hint">Showing first {MAX_RESULTS} of {tickers.length} - keep typing to narrow down</li>
          )}
        </ul>
      )}
    </div>
  )
}
