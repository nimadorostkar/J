import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Download, RefreshCw, X } from 'lucide-react'
import { useT } from '../i18n/LanguageContext.jsx'
import { applyUpdate, pwaBus } from './registerSW.js'

const INSTALL_DISMISS_KEY = 'tv.pwa.installDismissed'

/**
 * Two stacked toasts at the bottom of the viewport:
 *   • Install banner — visible when the browser fires `beforeinstallprompt`
 *     and the user hasn't dismissed it.
 *   • Update banner — visible when a new service worker is waiting.
 *
 * Both are non-blocking — they sit above the bottom nav and the user can
 * dismiss them without losing functionality.
 */
export default function PwaPrompts() {
  const t = useT()
  const [installEvent, setInstallEvent] = useState(null)
  const [updateReady, setUpdateReady] = useState(false)
  const [installed, setInstalled] = useState(
    typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(display-mode: standalone)').matches,
  )

  // Capture beforeinstallprompt so we can fire .prompt() on user gesture.
  useEffect(() => {
    const onBeforeInstall = (e) => {
      e.preventDefault()
      // Respect a prior dismissal — don't nag every visit.
      try {
        if (localStorage.getItem(INSTALL_DISMISS_KEY)) return
      } catch {}
      setInstallEvent(e)
    }
    const onInstalled = () => {
      setInstalled(true)
      setInstallEvent(null)
    }
    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  // Listen for SW update events.
  useEffect(() => {
    const onUpdate = () => setUpdateReady(true)
    pwaBus.addEventListener('update-available', onUpdate)
    return () => pwaBus.removeEventListener('update-available', onUpdate)
  }, [])

  const onInstall = async () => {
    if (!installEvent) return
    try {
      installEvent.prompt()
      await installEvent.userChoice
    } catch {}
    setInstallEvent(null)
  }

  const onDismissInstall = () => {
    setInstallEvent(null)
    try { localStorage.setItem(INSTALL_DISMISS_KEY, String(Date.now())) } catch {}
  }

  const showInstall = !!installEvent && !installed
  const showUpdate = updateReady

  return (
    <div
      className="fixed left-1/2 -translate-x-1/2 z-50 w-full max-w-[460px] px-4 pointer-events-none"
      style={{ bottom: 'calc(72px + env(safe-area-inset-bottom))' }}
    >
      <AnimatePresence>
        {showUpdate && (
          <motion.div
            key="update"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.25 }}
            className="pointer-events-auto mb-2 flex items-center gap-3 rounded-2xl border border-teal-400/50 bg-space-700/95 backdrop-blur-xl px-3.5 py-2.5 shadow-card"
          >
            <RefreshCw size={16} className="text-teal-300 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-white">{t('pwa.updateTitle')}</div>
              <div className="text-[11px] text-gray-400 truncate">{t('pwa.updateDesc')}</div>
            </div>
            <button
              type="button"
              onClick={applyUpdate}
              className="h-8 px-3 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 text-xs font-semibold transition shrink-0"
            >
              {t('pwa.refresh')}
            </button>
          </motion.div>
        )}

        {showInstall && (
          <motion.div
            key="install"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            transition={{ duration: 0.25 }}
            className="pointer-events-auto flex items-center gap-3 rounded-2xl border border-space-500 bg-space-700/95 backdrop-blur-xl px-3.5 py-2.5 shadow-card"
          >
            <Download size={16} className="text-teal-300 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-white">{t('pwa.installTitle')}</div>
              <div className="text-[11px] text-gray-400 truncate">{t('pwa.installDesc')}</div>
            </div>
            <button
              type="button"
              onClick={onInstall}
              className="h-8 px-3 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 text-xs font-semibold transition shrink-0"
            >
              {t('pwa.install')}
            </button>
            <button
              type="button"
              onClick={onDismissInstall}
              aria-label={t('common.close')}
              className="h-8 w-8 grid place-items-center rounded-full text-gray-400 hover:text-white transition shrink-0"
            >
              <X size={14} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
