import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, X } from 'lucide-react'

const MAX_RESULTS = 50

/**
 * One control for building a list of tickers two ways at once:
 *  - type to search (by symbol or name) and click/Enter to add one, or
 *  - paste a comma-separated blob and every valid symbol in it becomes a
 *    chip in one shot.
 * Both paths feed the same `value` array, so switching between "search for
 * a couple of names" and "paste a list I already have" needs no mode switch.
 */
export default function TickerMultiSelect({ tickers, tickerNames, value, onChange, placeholder, disabled, showBulkActions }) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [invalidTickers, setInvalidTickers] = useState([])
  const containerRef = useRef(null)
  const inputRef = useRef(null)

  const tickerSet = useMemo(() => new Set(tickers), [tickers])
  const selectedSet = useMemo(() => new Set(value), [value])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const pool = q
      ? tickers.filter((t) => t.toLowerCase().includes(q) || (tickerNames?.[t] || '').toLowerCase().includes(q))
      : tickers.filter((t) => !selectedSet.has(t))
    return pool.slice(0, MAX_RESULTS)
  }, [query, tickers, tickerNames, selectedSet])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const addTicker = (t) => {
    if (!selectedSet.has(t)) onChange([...value, t])
  }

  const removeTicker = (t) => {
    onChange(value.filter((x) => x !== t))
  }

  // A paste (or any input that lands with commas already in it) is treated
  // as a full CSV list, not a single search term - every valid symbol in it
  // becomes a chip immediately instead of waiting for the user to pick one.
  const ingestCsv = (raw) => {
    const inputs = raw.split(',').map((t) => t.trim().toUpperCase()).filter(Boolean)
    const valid = []
    const invalid = []
    for (const t of inputs) {
      if (tickerSet.has(t)) {
        if (!selectedSet.has(t) && !valid.includes(t)) valid.push(t)
      } else if (!invalid.includes(t)) {
        invalid.push(t)
      }
    }
    if (valid.length > 0) onChange([...value, ...valid])
    setInvalidTickers(invalid)
    setQuery('')
    setOpen(false)
  }

  const handlePaste = (e) => {
    const text = e.clipboardData.getData('text')
    if (text.includes(',')) {
      e.preventDefault()
      ingestCsv(text)
    }
  }

  const handleChange = (e) => {
    const val = e.target.value
    if (val.includes(',')) {
      ingestCsv(val)
      return
    }
    setQuery(val)
    setOpen(true)
    setHighlighted(0)
    setInvalidTickers([])
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
      if (query.trim()) {
        // Enter on free-typed text with no dropdown match selected yet -
        // treat it the same as a paste, so typing SBIN and hitting Enter
        // works without requiring a click.
        ingestCsv(query)
      } else if (filtered[highlighted]) {
        addTicker(filtered[highlighted])
        setQuery('')
      }
    } else if (e.key === 'Backspace' && !query && value.length > 0) {
      removeTicker(value[value.length - 1])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div>
      <div className="ticker-combobox" ref={containerRef}>
        <div className="ticker-combobox-input-wrap">
          <input
            ref={inputRef}
            type="text"
            className="form-input"
            placeholder={placeholder || 'Search or paste comma-separated tickers...'}
            value={query}
            onFocus={() => { setOpen(true); setHighlighted(0) }}
            onChange={handleChange}
            onPaste={handlePaste}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            autoComplete="off"
          />
          <ChevronDown size={14} className="ticker-combobox-chevron" />
        </div>

        {open && !disabled && (
          <ul className="ticker-combobox-list">
            {filtered.length === 0 && <li className="ticker-combobox-empty">No matching tickers</li>}
            {filtered.map((t, i) => (
              <li
                key={t}
                className={`ticker-combobox-option ${i === highlighted ? 'highlighted' : ''}`}
                onMouseDown={() => { addTicker(t); setQuery(''); inputRef.current?.focus() }}
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
              <li className="ticker-combobox-hint">Showing first {MAX_RESULTS} - keep typing to narrow down</li>
            )}
          </ul>
        )}
      </div>

      {invalidTickers.length > 0 && (
        <div className="form-hint" style={{ color: 'var(--negative)', marginTop: '0.4rem' }}>
          Invalid tickers ignored: {invalidTickers.join(', ')}
        </div>
      )}

      {showBulkActions && (
        <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.4rem' }}>
          <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}
            onClick={() => onChange(tickers)} disabled={disabled}>
            Select All
          </button>
          <button type="button" className="btn-secondary" style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem', color: 'var(--negative)', borderColor: 'var(--negative)' }}
            onClick={() => onChange([])} disabled={disabled || value.length === 0}>
            Clear
          </button>
        </div>
      )}

      <div className="ticker-chip-list">
        {value.length === 0 && <span className="form-hint" style={{ padding: '0.25rem' }}>No tickers selected yet.</span>}
        {value.map((t) => (
          <span key={t} className="ticker-chip">
            {t}
            {!disabled && (
              <button type="button" onClick={() => removeTicker(t)} aria-label={`Remove ${t}`}>
                <X size={12} />
              </button>
            )}
          </span>
        ))}
      </div>
    </div>
  )
}
