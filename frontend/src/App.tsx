import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth'
import { useAuth } from './useAuth'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { DefectDetail } from './pages/DefectDetail'
import { Defects } from './pages/Defects'
import { Login } from './pages/Login'
import { NewDefect } from './pages/NewDefect'

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <p className="muted center">Loading…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Dashboard />} />
        <Route path="defects" element={<Defects />} />
        <Route path="defects/new" element={<NewDefect />} />
        <Route path="defects/:key" element={<DefectDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
