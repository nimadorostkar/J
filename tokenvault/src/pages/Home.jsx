import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import StarField from '../components/StarField.jsx'
import { useWallet } from '../context/WalletContext.jsx'
import houstonLogo from '/houston-logo.png'
import spaceBg from '/space-bg.jpg'

function formatRemaining(endTime) {
  if (!endTime) return '—'
  const t = Math.max(0, endTime - Date.now())
  const days = Math.floor(t / (24 * 3600 * 1000))
  const hours = Math.floor((t / (3600 * 1000)) % 24)
  const minutes = Math.floor((t / (60 * 1000)) % 60)
  return `${days} day ${hours} hour ${minutes} minutes`
}

export default function Home() {
  const { wallet } = useWallet()
  const endTime = wallet?.globalCycleEnd
  const [text, setText] = useState(() => formatRemaining(endTime))

  useEffect(() => {
    setText(formatRemaining(endTime))
    if (!endTime) return
    const id = setInterval(() => setText(formatRemaining(endTime)), 1000)
    return () => clearInterval(id)
  }, [endTime])

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

        <span className="text-white text-[12px]">{text}</span>
      </div>
    </div>
  )
}
