import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setUnauthorizedHandler, tokenStore } from './api'
import type { Role, User } from './types'
import { AuthContext, type AuthState } from './useAuth'

const RANK: Record<Role, number> = { viewer: 0, engineer: 1, lead: 2, admin: 3 }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => tokenStore.get() !== null)

  const logout = useCallback(() => {
    tokenStore.set(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!tokenStore.get()) return
    api
      .me()
      .then(setUser)
      .catch(logout)
      .finally(() => setLoading(false))
  }, [logout])

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      async login(username, password) {
        const result = await api.login(username, password)
        tokenStore.set(result.access_token)
        setUser(result.user)
      },
      logout,
      can: (minimum) => user !== null && RANK[user.role] >= RANK[minimum],
    }),
    [user, loading, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
