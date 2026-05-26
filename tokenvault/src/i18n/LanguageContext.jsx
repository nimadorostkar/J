import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { translations } from './translations.js'

// Supported languages with their native labels and direction.
export const LANGUAGES = [
  { code: 'en', label: 'English',  native: 'English',   dir: 'ltr', flag: '🇬🇧' },
  { code: 'de', label: 'German',   native: 'Deutsch',   dir: 'ltr', flag: '🇩🇪' },
  { code: 'fa', label: 'Farsi',    native: 'فارسی',     dir: 'rtl', flag: '🇮🇷' },
  { code: 'ar', label: 'Arabic',   native: 'العربية',   dir: 'rtl', flag: '🇸🇦' },
  { code: 'tr', label: 'Turkish',  native: 'Türkçe',    dir: 'ltr', flag: '🇹🇷' },
  { code: 'es', label: 'Spanish',  native: 'Español',   dir: 'ltr', flag: '🇪🇸' },
]

const STORAGE_KEY = 'tv.lang'
const FALLBACK = 'en'

function detectInitial() {
  if (typeof window === 'undefined') return FALLBACK
  const stored = window.localStorage?.getItem(STORAGE_KEY)
  if (stored && LANGUAGES.some((l) => l.code === stored)) return stored
  const nav = (navigator.language || navigator.userLanguage || '').toLowerCase()
  const short = nav.split('-')[0]
  if (LANGUAGES.some((l) => l.code === short)) return short
  return FALLBACK
}

// Resolve a dotted key path (e.g. "wallet.title") inside a dictionary.
function lookup(dict, key) {
  if (!dict || !key) return undefined
  if (Object.prototype.hasOwnProperty.call(dict, key)) return dict[key]
  const parts = key.split('.')
  let cur = dict
  for (const p of parts) {
    if (cur && typeof cur === 'object' && p in cur) cur = cur[p]
    else return undefined
  }
  return cur
}

// Replace {name} placeholders with values from `vars`.
function interpolate(template, vars) {
  if (typeof template !== 'string' || !vars) return template
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    vars[k] !== undefined && vars[k] !== null ? String(vars[k]) : `{${k}}`,
  )
}

const LanguageContext = createContext({
  lang: FALLBACK,
  dir: 'ltr',
  setLang: () => {},
  t: (k) => k,
  languages: LANGUAGES,
})

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(() => detectInitial())

  const setLang = useCallback((code) => {
    if (!LANGUAGES.some((l) => l.code === code)) return
    setLangState(code)
    try { window.localStorage.setItem(STORAGE_KEY, code) } catch {}
  }, [])

  const meta = LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0]
  const dir = meta.dir

  // Reflect direction + language at the document level so global CSS can react.
  useEffect(() => {
    if (typeof document === 'undefined') return
    document.documentElement.setAttribute('lang', lang)
    document.documentElement.setAttribute('dir', dir)
  }, [lang, dir])

  const t = useCallback(
    (key, vars) => {
      const primary = lookup(translations[lang], key)
      if (primary !== undefined) return interpolate(primary, vars)
      const fallback = lookup(translations[FALLBACK], key)
      if (fallback !== undefined) return interpolate(fallback, vars)
      return key
    },
    [lang],
  )

  const value = useMemo(
    () => ({ lang, dir, setLang, t, languages: LANGUAGES }),
    [lang, dir, setLang, t],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage() {
  return useContext(LanguageContext)
}

// Convenience hook so components can write `const t = useT()`.
export function useT() {
  return useContext(LanguageContext).t
}
