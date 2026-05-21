import { createContext, useContext, useEffect, useState } from 'react'

const AuthContext = createContext(null)

const DEFAULT_USER = {
  id: 'usr_001',
  firstName: 'Alex',
  lastName: 'Morgan',
  email: 'alex@example.com',
  mobile: '+1 555 0100',
  country: 'United States',
  referralCode: 'ALEX2024',
  hasDeposit: true,
  hasReferral: true,
  joinDate: '2024-01-15',
}

const STORAGE_KEY = 'houston.user'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else localStorage.removeItem(STORAGE_KEY)
  }, [user])

  const login = ({ email, password }) => {
    if (!email || !password || password.length < 6) {
      throw new Error('Invalid credentials')
    }
    const next = { ...DEFAULT_USER, email }
    setUser(next)
    return next
  }

  const register = (data) => {
    const next = {
      ...DEFAULT_USER,
      firstName: data.firstName || DEFAULT_USER.firstName,
      lastName: data.lastName || DEFAULT_USER.lastName,
      email: data.email,
      mobile: data.mobile || DEFAULT_USER.mobile,
      country: data.country || DEFAULT_USER.country,
      referralCode: (data.firstName?.toUpperCase() || 'USER') + '2024',
      hasDeposit: false,
      hasReferral: false,
      joinDate: new Date().toISOString().slice(0, 10),
    }
    setUser(next)
    return next
  }

  const updateUser = (patch) => setUser((u) => (u ? { ...u, ...patch } : u))
  const logout = () => setUser(null)

  return (
    <AuthContext.Provider value={{ user, login, register, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
