import { createContext, useCallback, useContext, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

const VARIANT_STYLES = {
  success: { bg: 'bg-emerald-500/15', border: 'border-emerald-400/40', text: 'text-emerald-300', Icon: CheckCircle2 },
  error: { bg: 'bg-rose-500/15', border: 'border-rose-400/40', text: 'text-rose-300', Icon: AlertCircle },
  info: { bg: 'bg-teal-500/15', border: 'border-teal-400/40', text: 'text-teal-300', Icon: Info },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const showToast = useCallback((message, variant = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, message, variant }])
    setTimeout(() => dismiss(id), 3000)
  }, [dismiss])

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-4 left-0 right-0 z-[9999] flex flex-col items-center gap-2 px-4 pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => {
            const v = VARIANT_STYLES[toast.variant] || VARIANT_STYLES.info
            const Icon = v.Icon
            return (
              <motion.div
                key={toast.id}
                initial={{ y: -40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: -20, opacity: 0 }}
                transition={{ type: 'spring', stiffness: 320, damping: 26 }}
                className={`pointer-events-auto flex items-center gap-3 rounded-2xl border backdrop-blur-xl px-4 py-3 shadow-card ${v.bg} ${v.border} ${v.text}`}
              >
                <Icon size={18} />
                <span className="text-sm font-medium text-white">{toast.message}</span>
                <button onClick={() => dismiss(toast.id)} aria-label="Dismiss" className="opacity-60 hover:opacity-100 transition">
                  <X size={14} />
                </button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
