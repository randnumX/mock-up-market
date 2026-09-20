import { useEffect, useState, useCallback } from 'react'

const STORAGE_KEY = 'mock-up-market-theme'

function getInitialTheme() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage unavailable (private mode, etc.) - fall through to system preference
  }
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

/**
 * Single source of truth for light/dark mode - both the toggle button
 * (Header) and anything that needs to know the *current* theme in JS, not
 * just CSS (EquityChart: lightweight-charts takes literal color strings,
 * not CSS variables, so it has to be told which palette to use and
 * rebuilt when the theme changes).
 */
export function useTheme() {
  const [theme, setTheme] = useState(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // ignore - per-viewer convenience only
    }
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  }, [])

  return { theme, toggleTheme }
}
