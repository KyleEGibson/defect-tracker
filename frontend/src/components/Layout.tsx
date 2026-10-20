import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../useAuth'

export function Layout() {
  const { user, logout, can } = useAuth()
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">CAPA Tracker</span>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/defects">Defects</NavLink>
          {can('engineer') && <NavLink to="/defects/new">Report defect</NavLink>}
        </nav>
        <span className="who">
          {user?.full_name} <span className="role">{user?.role}</span>
          <button type="button" className="link" onClick={logout}>Sign out</button>
        </span>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
