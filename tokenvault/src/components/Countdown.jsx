import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'

function diff(endMs) {
  const t = Math.max(0, endMs - Date.now())
  const days = Math.floor(t / (24 * 3600 * 1000))
  const hours = Math.floor((t / (3600 * 1000)) % 24)
  const minutes = Math.floor((t / (60 * 1000)) % 60)
  const seconds = Math.floor((t / 1000) % 60)
  return { days, hours, minutes, seconds, total: t }
}

const pad = (n) => String(n).padStart(2, '0')

export default function Countdown({ endTime, variant = 'teal', hideDays = false }) {
  const [now, setNow] = useState(() => diff(endTime))

  useEffect(() => {
    setNow(diff(endTime))
    const id = setInterval(() => setNow(diff(endTime)), 1000)
    return () => clearInterval(id)
  }, [endTime])

  const blocks = useMemo(() => {
    const base = [
      { label: 'DAYS', value: pad(now.days) },
      { label: 'HRS', value: pad(now.hours) },
      { label: 'MIN', value: pad(now.minutes) },
      { label: 'SEC', value: pad(now.seconds) },
    ]
    return hideDays ? base.slice(1) : base
  }, [now, hideDays])

  const colorMap = {
    teal: {
      card: 'border-teal-400/50 shadow-teal-glow',
      digit: 'text-white',
      label: 'text-teal-400',
      sep: 'text-teal-400',
    },
    gold: {
      card: 'border-gold-400/60 shadow-gold-glow',
      digit: 'text-white',
      label: 'text-gold-400',
      sep: 'text-gold-400',
    },
  }
  const c = colorMap[variant] || colorMap.teal

  return (
    <div className="flex items-end justify-center gap-2 sm:gap-3">
      {blocks.map((b, i) => (
        <div key={b.label} className="flex items-end gap-2 sm:gap-3">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * i, type: 'spring', stiffness: 280, damping: 22 }}
            className="flex flex-col items-center"
          >
            <div
              className={`bg-space-600 border rounded-2xl ${c.card} w-[70px] sm:w-[78px] h-[88px] sm:h-[96px] flex items-center justify-center`}
            >
              <span className={`font-mono font-bold text-[40px] sm:text-[44px] leading-none ${c.digit}`}>
                {b.value}
              </span>
            </div>
            <span className={`mt-2 text-[10px] tracking-[0.18em] font-semibold ${c.label}`}>
              {b.label}
            </span>
          </motion.div>
          {i < blocks.length - 1 && (
            <span className={`mb-7 font-mono font-bold text-3xl ${c.sep} animate-blink`}>:</span>
          )}
        </div>
      ))}
    </div>
  )
}
