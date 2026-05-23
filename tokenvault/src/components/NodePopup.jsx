import { AnimatePresence, motion } from 'framer-motion'
import { Check, CircleDot, Mail, Coins, Award } from 'lucide-react'

function initials(name) {
  return name.split(' ').map((p) => p[0]).slice(0, 2).join('')
}

// Four-step pipeline. Each step "fires" once the corresponding fact is true.
const STATUS_STEPS = [
  { code: 'registered',              label: 'Registered',              icon: CircleDot },
  { code: 'verified',                label: 'Email Verified',          icon: Mail },
  { code: 'first_deposit_completed', label: 'First Deposit Completed', icon: Coins },
  { code: 'qualified',               label: 'Qualified Referral',      icon: Award },
]

function activeIndex(node) {
  // Pick the highest step that's true. Each downstream step strictly implies
  // the upstream ones, so we walk top-down.
  if (node.isQualified) return 3
  if (node.hasDeposit) return 2
  if (node.isVerified) return 1
  return 0
}

export default function NodePopup({ node, onClose }) {
  return (
    <AnimatePresence>
      {node && (
        <motion.div
          className="fixed inset-0 z-40 flex items-center justify-center p-6"
          initial={{ backgroundColor: 'rgba(0,0,0,0)' }}
          animate={{ backgroundColor: 'rgba(0,0,0,0.55)' }}
          exit={{ backgroundColor: 'rgba(0,0,0,0)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 360, damping: 26 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-[340px] rounded-2xl bg-space-700 border border-space-500 p-5 shadow-card"
          >
            <div className="flex items-center gap-3">
              {node.avatar ? (
                <img
                  src={node.avatar}
                  alt=""
                  className="h-14 w-14 rounded-full object-cover border-2 border-space-500"
                />
              ) : (
                <div
                  className={`h-14 w-14 rounded-full grid place-items-center font-bold text-white ${
                    node.level === 2
                      ? 'bg-gradient-to-br from-purple-400 to-purple-600'
                      : 'bg-gradient-to-br from-teal-400 to-teal-600'
                  }`}
                >
                  {initials(node.name)}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="font-semibold text-white truncate">{node.name}</div>
                <div className="text-xs text-gray-400">Joined {node.joined}</div>
              </div>
              <span
                className={`text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${
                  node.isQualified
                    ? 'bg-emerald-500/20 text-emerald-300'
                    : 'bg-amber-500/20 text-amber-300'
                }`}
                title={
                  node.isQualified
                    ? 'Counts toward milestone rewards'
                    : 'Does not count toward milestones yet — waiting for first deposit'
                }
              >
                {node.isQualified ? 'Qualified' : 'Pending'}
              </span>
            </div>

            {/* Status pipeline */}
            <div className="mt-5">
              <div className="text-[10px] font-bold tracking-[0.12em] text-white/50 uppercase mb-2">
                Status
              </div>
              <ol className="space-y-1.5">
                {STATUS_STEPS.map((s, i) => {
                  const reached = activeIndex(node) >= i
                  const Icon = s.icon
                  return (
                    <li
                      key={s.code}
                      className={`flex items-center gap-2 text-[12.5px] ${
                        reached ? 'text-white' : 'text-gray-500'
                      }`}
                    >
                      <span
                        className={`h-5 w-5 rounded-full grid place-items-center ${
                          reached
                            ? (i === 3
                                ? 'bg-emerald-500/30 text-emerald-300'
                                : 'bg-teal-500/25 text-teal-300')
                            : 'bg-space-600 text-gray-600'
                        }`}
                      >
                        {reached ? <Check size={12} /> : <Icon size={11} />}
                      </span>
                      <span>{s.label}</span>
                    </li>
                  )
                })}
              </ol>
              {!node.isQualified && node.level === 1 && (
                <p className="mt-3 text-[11px] text-amber-200/80 leading-snug italic">
                  Only invited users who complete at least one deposit count
                  toward your milestone rewards.
                </p>
              )}
              {node.level === 2 && (
                <p className="mt-3 text-[11px] text-gray-400 leading-snug italic">
                  Level-2 referrals don't count toward milestone rewards — only
                  your direct (Level-1) invites do.
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={onClose}
              className="w-full mt-5 h-10 rounded-full bg-space-600 hover:bg-space-500 text-sm text-white transition"
            >
              Close
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
