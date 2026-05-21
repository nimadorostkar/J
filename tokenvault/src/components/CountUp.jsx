import { useEffect, useState } from 'react'

export default function CountUp({ to, duration = 1500, decimals = 0, className = '' }) {
  const [n, setN] = useState(0)

  useEffect(() => {
    let raf
    const start = performance.now()
    const tick = (t) => {
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3) // easeOutCubic
      setN(to * eased)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [to, duration])

  return <span className={className}>{n.toFixed(decimals)}</span>
}
