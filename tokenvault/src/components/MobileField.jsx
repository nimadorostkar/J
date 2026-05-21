import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Search } from 'lucide-react'
import { COUNTRY_CODES } from '../data/network.js'

export default function MobileField({
  label = 'Mobile',
  code,
  number,
  onCodeChange,
  onNumberChange,
  error,
  placeholder = '555 0100',
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const wrapRef = useRef(null)

  // Close on outside click or Escape
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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return COUNTRY_CODES
    return COUNTRY_CODES.filter(
      (c) =>
        c.country.toLowerCase().includes(q) ||
        c.code.includes(q) ||
        c.flag.toLowerCase().includes(q),
    )
  }, [query])

  const selected = COUNTRY_CODES.find((c) => c.code === code) || COUNTRY_CODES[0]

  return (
    <div className="relative" ref={wrapRef}>
      <span className="block text-xs font-medium text-gray-400 mb-1.5 tracking-wide">
        {label}
      </span>
      <div
        className={`flex items-stretch bg-space-600 border rounded-xl min-h-[48px] overflow-hidden transition focus-within:border-teal-400 focus-within:ring-2 focus-within:ring-teal-400/30 ${
          error ? 'border-rose-400/60' : 'border-space-500'
        }`}
      >
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 px-3 text-sm text-white border-r border-space-500 hover:bg-space-500/60 transition shrink-0"
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className="text-xs font-semibold text-gray-300 tracking-wider">{selected.flag}</span>
          <span className="font-mono text-sm">{selected.code}</span>
          <ChevronDown size={14} className="text-gray-400" />
        </button>
        <input
          type="tel"
          inputMode="numeric"
          value={number}
          onChange={(e) => onNumberChange(e.target.value)}
          placeholder={placeholder}
          className="flex-1 bg-transparent outline-none text-white placeholder:text-gray-500 text-[15px] min-w-0 px-3"
        />
      </div>
      {error && <span className="block text-xs text-rose-400 mt-1.5">{error}</span>}

      {open && (
        <div
          role="listbox"
          className="absolute z-30 mt-2 left-0 right-0 max-h-72 overflow-hidden rounded-xl border border-space-500 bg-space-700 shadow-card"
        >
          <div className="flex items-center gap-2 px-3 py-2 border-b border-space-500 bg-space-800">
            <Search size={14} className="text-gray-400" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search country or code"
              className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-gray-500"
            />
          </div>
          <div className="max-h-56 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-4 text-xs text-gray-500 text-center">No matches</div>
            ) : (
              filtered.map((c) => {
                const active = c.code === code && c.flag === selected.flag
                return (
                  <button
                    key={`${c.code}-${c.flag}`}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onCodeChange(c.code)
                      setOpen(false)
                      setQuery('')
                    }}
                    className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-space-600 transition ${
                      active ? 'bg-teal-500/10 text-teal-200' : 'text-white'
                    }`}
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-semibold text-gray-400 w-6 shrink-0">{c.flag}</span>
                      <span className="truncate">{c.country}</span>
                    </span>
                    <span className="font-mono text-xs text-gray-300 shrink-0">{c.code}</span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
