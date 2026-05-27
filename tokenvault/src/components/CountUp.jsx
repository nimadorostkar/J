import { useEffect, useState } from 'react'

/**
 * Animated number counter.
 *
 * Props:
 *   to            – target number (required).
 *   duration      – animation duration in ms (default 1500).
 *   decimals      – FIXED number of decimal places (default 0).
 *                   Use this when you always want the same precision, e.g.
 *                     <CountUp to={value} decimals={2} />  →  "12.30"
 *   maxDecimals   – MAXIMUM decimal places; trailing zeros are stripped so
 *                   integer values stay clean. Wins over `decimals` when set.
 *                     <CountUp to={1.2}   maxDecimals={4} />  →  "1.2"
 *                     <CountUp to={1}     maxDecimals={4} />  →  "1"
 *                     <CountUp to={0.005} maxDecimals={4} />  →  "0.005"
 *   className     – passthrough.
 */
export default function CountUp({
  to,
  duration = 1500,
  decimals = 0,
  maxDecimals,
  className = '',
}) {
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

  const formatted =
    typeof maxDecimals === 'number'
      // Limit to maxDecimals then strip trailing zeros / dangling decimal
      // via `Number(...).toString()`. Locale-free so "1234.5" stays "1234.5".
      ? Number(n.toFixed(maxDecimals)).toString()
      : n.toFixed(decimals)

  return <span className={className}>{formatted}</span>
}
