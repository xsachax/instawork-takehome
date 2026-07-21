import { NavLink, Outlet } from 'react-router-dom'

const navClass = ({ isActive }) => (isActive ? 'active' : undefined)

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">Skip to main content</a>
      <header className="app-header">
        <div className="inner">
          <NavLink to="/" className="brand">🧠 Quiz Platform</NavLink>
          <nav className="app-nav" aria-label="Primary">
            <NavLink to="/" end className={navClass}>Play</NavLink>
            <NavLink to="/history" className={navClass}>My attempts</NavLink>
            <NavLink to="/admin" className={navClass}>Admin</NavLink>
          </nav>
        </div>
      </header>
      <main id="main">
        <Outlet />
      </main>
    </>
  )
}
