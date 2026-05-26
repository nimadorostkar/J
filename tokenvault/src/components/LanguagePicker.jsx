import { useEffect, useRef, useState } from 'react'
import { Globe, Check } from 'lucide-react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

/**
 * Compact language picker for screens where a full card would be overkill
 * (login / register / forgot password). Renders as a floating chip that
 * pops a small menu listing every supported language in its native script.
 *
 * `variant="absolute"` (default) positions itself in the top-right (or
 * top-left under RTL) of its nearest positioned ancestor. `variant="inline"`
 * leaves layout to the parent.
 */
export default function LanguagePicker({ variant = 'absolute' }) {
  const { lang, setLang, languages, dir } = useLanguage()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)
  const current = languages.find((l) => l.code === lang) || languages[0]

  // Close on outside click + Escape
  useEffect(() => {
    if (!open) return
    const onClick = (e) => {
      if (!wrapRef.current?.contains(e.target)) setOpen(false)
    }
    const onKey = (e) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  // In RTL, drop the floating chip on the LEFT corner so it stays in the
  // visual "leading" position (mirroring the LTR top-right placement).
  const positionCls =
    variant === 'absolute'
      ? `absolute top-4 ${dir === 'rtl' ? 'left-4' : 'right-4'} z-20`
      : 'relative'

  return (
    <div className={positionCls} ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="flex items-center gap-1.5 h-9 px-3 rounded-full bg-space-700/80 backdrop-blur-xl border border-space-500 text-xs text-white hover:border-teal-400 transition shadow-card"
      >
        <Globe size={14} className="text-teal-300" />
        <span className="text-base leading-none">{current.flag}</span>
        <span className="font-medium">{current.code.toUpperCase()}</span>
      </button>

      {open && (
        <div
          role="listbox"
          className={`absolute mt-2 ${
            dir === 'rtl' ? 'left-0' : 'right-0'
          } min-w-[160px] rounded-2xl border border-space-500 bg-space-700/95 backdrop-blur-xl shadow-card overflow-hidden`}
        >
          {languages.map((l) => {
            const active = l.code === lang
            return (
              <button
                key={l.code}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => {
                  setLang(l.code)
                  setOpen(false)
                }}
                className={`w-full flex items-center gap-2 px-3 py-2.5 text-sm transition text-start ${
                  active ? 'bg-teal-500/15 text-teal-200' : 'text-white hover:bg-space-600'
                }`}
              >
                <span className="text-base leading-none">{l.flag}</span>
                <span className="flex-1 truncate">{l.native}</span>
                {active && <Check size={14} className="shrink-0 text-teal-300" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
