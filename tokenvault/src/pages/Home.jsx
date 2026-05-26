import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import { useWallet } from '../context/WalletContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import houstonLogo from '/houston-logo.png'
import spaceBg from '/space-bg.jpg'

function remainingParts(endTime) {
  if (!endTime) return null
  const t = Math.max(0, endTime - Date.now())
  return {
    days: Math.floor(t / (24 * 3600 * 1000)),
    hours: Math.floor((t / (3600 * 1000)) % 24),
    minutes: Math.floor((t / (60 * 1000)) % 60),
  }
}

export default function Home() {
  const { wallet } = useWallet()
  const t = useT()
  const endTime = wallet?.globalCycleEnd
  const [parts, setParts] = useState(() => remainingParts(endTime))

  useEffect(() => {
    setParts(remainingParts(endTime))
    if (!endTime) return
    const id = setInterval(() => setParts(remainingParts(endTime)), 1000)
    return () => clearInterval(id)
  }, [endTime])

  const text = parts ? t('home.duration', parts) : '—'

  return (
    <div className="relative min-h-[100dvh] w-full overflow-hidden bg-space-900 flex items-start justify-center px-5 pt-[25vh] pb-20">
      <StarField />
      <div
        className="pointer-events-none absolute inset-0 z-[1] opacity-10"
        style={{
          backgroundImage: `url(${spaceBg})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
        aria-hidden
      />

      <div className="relative z-10 w-full max-w-[480px] flex flex-col items-center text-center gap-7">
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center justify-center"
        >
          <img
            src={houstonLogo}
            alt="Houston"
            className="h-[72px] sm:h-[84px] w-auto select-none drop-shadow-[0_0_18px_rgba(45,212,191,0.35)]"
            draggable="false"
          />
        </motion.div>

        <div className="flex flex-col items-center gap-1">
          <span className="text-white text-[12px]">{text}</span>
          <span className="text-gray-400 text-[11px] tracking-wide">
            {t('home.untilIco')}
          </span>
        </div>
      </div>
    </div>
  )
}
