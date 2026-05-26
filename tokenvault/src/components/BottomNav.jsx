import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Timer, Wallet, Share2, User, Bot } from 'lucide-react'
import { useT } from '../i18n/LanguageContext.jsx'

const TABS = [
  { to: '/home', labelKey: 'nav.home', Icon: Timer },
  { to: '/wallet', labelKey: 'nav.wallet', Icon: Wallet },
  { to: '/trade', labelKey: 'nav.trade', Icon: Bot },
  { to: '/network', labelKey: 'nav.network', Icon: Share2 },
  { to: '/profile', labelKey: 'nav.profile', Icon: User },
]

export default function BottomNav() {
  const { pathname } = useLocation()
  const t = useT()

  return (
    <nav
      className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[480px] z-40"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <div
        className="flex items-stretch justify-around border-t border-space-500 backdrop-blur-xl"
        style={{ background: 'rgba(10, 14, 26, 0.9)', height: '64px' }}
      >
        {TABS.map(({ to, labelKey, Icon }) => {
          const active = pathname.startsWith(to)
          const label = t(labelKey)
          return (
            <NavLink
              key={to}
              to={to}
              className="relative flex-1 flex flex-col items-center justify-center gap-1 select-none"
            >
              {active && (
                <motion.div
                  layoutId="active-tab-indicator"
                  className="absolute top-0 h-[2px] w-10 bg-teal-400 rounded-full"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              <motion.div
                animate={{ scale: active ? 1.05 : 1, y: active ? -1 : 0 }}
                transition={{ type: 'spring', stiffness: 380, damping: 24 }}
              >
                <Icon
                  size={22}
                  strokeWidth={active ? 2.4 : 1.8}
                  className={active ? 'text-teal-400' : 'text-gray-500'}
                  fill={active ? 'rgba(45, 212, 191, 0.18)' : 'none'}
                />
              </motion.div>
              <span
                className={`text-[11px] font-medium tracking-wide ${
                  active ? 'text-teal-400' : 'text-gray-500'
                }`}
              >
                {label}
              </span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
