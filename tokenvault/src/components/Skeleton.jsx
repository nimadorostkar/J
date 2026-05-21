export default function Skeleton({ variant = 'line', className = '' }) {
  const base = 'rounded-xl shimmer'
  const variants = {
    line: 'h-3 w-full',
    card: 'h-28 w-full',
    avatar: 'h-12 w-12 rounded-full',
    'transaction-row': 'h-14 w-full',
  }
  return <div className={`${base} ${variants[variant] || variants.line} ${className}`} />
}

export function TransactionSkeleton() {
  return (
    <div className="flex items-center gap-3 py-3 px-1">
      <Skeleton variant="avatar" className="!h-10 !w-10" />
      <div className="flex-1 space-y-2">
        <Skeleton variant="line" className="!h-3 !w-3/5" />
        <Skeleton variant="line" className="!h-2 !w-2/5" />
      </div>
      <div className="space-y-2 text-right">
        <Skeleton variant="line" className="!h-3 !w-14 ml-auto" />
        <Skeleton variant="line" className="!h-2 !w-10 ml-auto" />
      </div>
    </div>
  )
}
