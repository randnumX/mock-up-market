import { TrendingUp } from 'lucide-react'

export default function Header() {
  return (
    <header className="header">
      <div className="header-logo">
        <div className="header-logo-icon"><TrendingUp size={20} strokeWidth={2.5} /></div>
        <div>
          <div className="header-title">Mock-Up Market</div>
          <div className="header-subtitle">Algorithmic Trading Engine</div>
        </div>
      </div>
    </header>
  )
}
