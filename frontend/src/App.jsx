import { useEffect, useRef } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const navClass = ({ isActive }) => (isActive ? 'active' : undefined)

export default function App() {
  const location = useLocation()
  const mainRef = useRef(null)
  const firstRender = useRef(true)

  // Move focus to the main region on client-side navigation so keyboard and
  // screen-reader users land in the new content instead of staying on a stale
  // control. Skipped on the initial render to leave the skip link reachable.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    mainRef.current?.focus()
  }, [location.pathname])

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
      <main id="main" ref={mainRef} tabIndex={-1}>
        <Outlet />
      </main>
    </>
  )
}
