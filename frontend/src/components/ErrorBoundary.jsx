import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Surfaced in the console so the actual failure is visible instead of a
    // silent blank screen - React unmounts the whole subtree on an uncaught
    // render error unless something catches it.
    console.error('Render error caught by ErrorBoundary:', error, info?.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="glass-card animate-in" style={{ borderColor: 'var(--negative)' }}>
          <div className="card-title" style={{ color: 'var(--negative)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertTriangle size={16} /> Something went wrong displaying this
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {this.state.error?.message || String(this.state.error)}
          </p>
          {this.props.onReset && (
            <button className="btn-secondary" onClick={() => { this.setState({ error: null }); this.props.onReset() }}>
              Go Back
            </button>
          )}
        </div>
      )
    }
    return this.props.children
  }
}
