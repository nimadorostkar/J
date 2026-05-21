export default function StarField({ className = '' }) {
  return (
    <div className={`pointer-events-none fixed inset-0 overflow-hidden ${className}`} aria-hidden>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_40%_30%,#0d1b3e_0%,#060A14_60%)]" />
      <div className="absolute inset-0 stars stars-1 animate-drift opacity-90" />
      <div className="absolute inset-0 stars stars-2 animate-drift-slow opacity-70" />
      <div className="absolute inset-0 stars stars-3 animate-drift-slow opacity-50" />
    </div>
  )
}
