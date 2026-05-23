import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { useAuth } from './context/AuthContext.jsx'
import BottomNav from './components/BottomNav.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import ForgotPassword from './pages/ForgotPassword.jsx'
import ResetPassword from './pages/ResetPassword.jsx'
import VerifyEmail from './pages/VerifyEmail.jsx'
import Home from './pages/Home.jsx'
import Wallet from './pages/Wallet.jsx'
import Network from './pages/Network.jsx'
import Profile from './pages/Profile.jsx'
import Trade from './pages/Trade.jsx'

function Protected({ children }) {
  const { user, status } = useAuth()
  if (status === 'loading') return <BootSplash />
  if (!user) return <Navigate to="/login" replace />
  return children
}

function Public({ children }) {
  const { user, status } = useAuth()
  if (status === 'loading') return <BootSplash />
  if (user) return <Navigate to="/home" replace />
  return children
}

function BootSplash() {
  return (
    <div className="min-h-[100dvh] grid place-items-center bg-space-900 text-teal-300">
      <span className="text-sm">Loading…</span>
    </div>
  )
}

const pageVariants = {
  initial: { opacity: 0, x: 18 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -18 },
}

function PageShell({ children }) {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="w-full"
    >
      {children}
    </motion.div>
  )
}

export default function App() {
  const location = useLocation()
  const { user } = useAuth()
  const isApp = ['/home', '/wallet', '/network', '/trade', '/profile'].some((p) =>
    location.pathname.startsWith(p),
  )

  return (
    <div className="min-h-[100dvh] w-full bg-space-900 text-white overflow-x-hidden">
      <div className="mx-auto w-full max-w-[480px] relative">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route
              path="/login"
              element={
                <Public>
                  <PageShell><Login /></PageShell>
                </Public>
              }
            />
            <Route
              path="/register"
              element={
                <Public>
                  <PageShell><Register /></PageShell>
                </Public>
              }
            />
            <Route
              path="/forgot-password"
              element={
                <Public>
                  <PageShell><ForgotPassword /></PageShell>
                </Public>
              }
            />
            <Route
              path="/reset-password"
              element={<PageShell><ResetPassword /></PageShell>}
            />
            <Route
              path="/verify-email"
              element={<PageShell><VerifyEmail /></PageShell>}
            />
            <Route
              path="/home"
              element={
                <Protected>
                  <PageShell><Home /></PageShell>
                </Protected>
              }
            />
            <Route
              path="/wallet"
              element={
                <Protected>
                  <PageShell><Wallet /></PageShell>
                </Protected>
              }
            />
            <Route
              path="/network"
              element={
                <Protected>
                  <PageShell><Network /></PageShell>
                </Protected>
              }
            />
            <Route
              path="/trade"
              element={
                <Protected>
                  <PageShell><Trade /></PageShell>
                </Protected>
              }
            />
            <Route
              path="/profile"
              element={
                <Protected>
                  <PageShell><Profile /></PageShell>
                </Protected>
              }
            />
            <Route
              path="*"
              element={<Navigate to={user ? '/home' : '/login'} replace />}
            />
          </Routes>
        </AnimatePresence>

        {isApp && user && <BottomNav />}
      </div>
    </div>
  )
}
