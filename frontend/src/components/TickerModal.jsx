import { X } from 'lucide-react'
import AssetChart from './AssetChart'

export default function TickerModal({ symbol, onClose }) {
  if (!symbol) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass-card animate-in" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span className="ticker-badge">{symbol}</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Historical Data (Daily)</span>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        
        <div className="modal-body" style={{ height: '400px', padding: '0 0.5rem 1rem 0.5rem' }}>
          <AssetChart symbol={symbol} />
        </div>
      </div>
    </div>
  )
}
