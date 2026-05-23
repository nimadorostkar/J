import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi, usersApi, tokenStore, onAuthChange, logoutLocally } from '../api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'idle' | 'loading' | 'ready'
  const [status, setStatus] = useState('idle')

  // On boot: if we have a refresh token, try to fetch the current user.
  // (the api client will auto-refresh access if needed)
  useEffect(() => {
    const hasRefresh = !!tokenStore.getRefresh()
    if (!hasRefresh) {
      setStatus('ready')
      return
    }
    setStatus('loading')
    usersApi
      .me()
      .then((me) => setUser(me))
      .catch(() => {
        tokenStore.clear()
        setUser(null)
      })
      .finally(() => setStatus('ready'))
  }, [])

  // Listen for auto-logout from api client (e.g., refresh failed).
  useEffect(() => {
    return onAuthChange((evt) => {
      if (evt.type === 'logout') setUser(null)
    })
  }, [])

  const login = useCallback(async ({ email, password }) => {
    const data = await authApi.login({ email, password })
    tokenStore.set(data.accessToken, data.refreshToken)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (payload) => {
    const data = await authApi.register(payload)
    tokenStore.set(data.accessToken, data.refreshToken)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try { await authApi.logout() } catch {}
    logoutLocally('user_logout')
    setUser(null)
  }, [])

  const refreshUser = useCallback(async () => {
    const me = await usersApi.me()
    setUser(me)
    return me
  }, [])

  const updateUser = useCallback(async (patch) => {
    const next = await usersApi.updateMe(patch)
    setUser((u) => ({ ...(u || {}), ...next }))
    return next
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, status, login, register, logout, updateUser, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
