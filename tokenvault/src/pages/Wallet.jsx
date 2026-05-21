import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bell,
  ArrowDownCircle,
  ArrowUpCircle,
  Star,
  Gift,
  ArrowUp,
  ArrowDown,
  Coins,
} from 'lucide-react'
import { useWallet } from '../context/WalletContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import Countdown from '../components/Countdown.jsx'
import CountUp from '../components/CountUp.jsx'
import { TransactionSkeleton } from '../components/Skeleton.jsx'
import DepositModal from '../components/DepositModal.jsx'
import WithdrawModal from '../components/WithdrawModal.jsx'

function txIcon(type) {
  if (type === 'deposit') return <ArrowUp size={16} className="text-emerald-400" />
  if (type === 'withdraw') return <ArrowDown size={16} className="text-rose-400" />
  return <Star size={16} className="text-gold-400" />
}

function txTint(type) {
  if (type === 'deposit') return 'bg-emerald-500/15 border-emerald-400/30'
  if (type === 'withdraw') return 'bg-rose-500/15 border-rose-400/30'
  return 'bg-gold-500/15 border-gold-400/30'
}

export default function WalletPage() {
  const { wallet, activateReward, claimReward } = useWallet()
  const { showToast } = useToast()
  const [loading, setLoading] = useState(true)
  const [showDeposit, setShowDeposit] = useState(false)
  const [showWithdraw, setShowWithdraw] = useState(false)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => setLoading(false), 1500)
    return () => clearTimeout(t)
  }, [])

  useEffect(() => {
    if (!wallet.rewardActive) return
    const id = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [wallet.rewardActive])

  const rewardReady =
    wallet.rewardActive && wallet.rewardEndTime && wallet.rewardEndTime <= Date.now()

  const onClaim = () => {
    claimReward()
    showToast('Claimed cycle reward!', 'success')
  }

  return (
    <div className="relative w-full max-w-[480px] mx-auto px-5 pt-6 pb-28 bg-space-900 min-h-[100dvh]">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold">Wallet</h1>
        <button
          type="button"
          aria-label="Notifications"
          className="h-10 w-10 grid place-items-center rounded-full border border-space-500 bg-space-700 hover:border-teal-400 transition"
        >
          <Bell size={18} className="text-gray-300" />
        </button>
      </div>

      {/* Balance Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="rounded-3xl border border-teal-400/40 bg-gradient-to-br from-teal-500/10 to-space-700 p-5 shadow-teal-glow"
      >
        <div className="text-xs text-gray-400 uppercase tracking-wider">Total Balance</div>
        <div className="flex items-center gap-3 mt-2">
          <div className="h-11 w-11 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 grid place-items-center shadow-gold-glow">
            <Coins size={22} className="text-amber-900" strokeWidth={2.5} />
          </div>
          <div className="font-mono font-bold text-[36px] leading-none">
            <CountUp to={wallet.hCoins} /> <span className="text-white">H Coins</span>
          </div>
        </div>
        <div className="text-gray-400 text-[15px] mt-2">
          ≈ <CountUp to={wallet.usdtBalance} decimals={2} /> USDT
        </div>
      </motion.div>

      {/* Next Reward */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.4 }}
        className="mt-4 rounded-3xl border border-gold-400/40 bg-gradient-to-br from-gold-500/10 to-space-700 p-5"
      >
        <div className="flex items-center gap-2 mb-3">
          <Gift size={18} className="text-gold-400" />
          <span className="text-sm font-semibold text-gold-300 uppercase tracking-wider">Next Reward</span>
        </div>
        {!wallet.rewardActive ? (
          <button
            type="button"
            onClick={() => {
              activateReward()
              showToast('Reward cycle activated!', 'success')
            }}
            className="w-full h-12 rounded-full bg-gold-500 hover:bg-gold-400 text-amber-950 font-semibold shadow-gold-glow active:scale-[0.98] transition"
          >
            Activate Reward Cycle
          </button>
        ) : rewardReady ? (
          <motion.button
            type="button"
            onClick={onClaim}
            animate={{ scale: [1, 1.03, 1] }}
            transition={{ duration: 1.4, repeat: Infinity }}
            className="w-full h-12 rounded-full bg-gold-500 text-amber-950 font-semibold shadow-gold-glow"
          >
            Claim Reward
          </motion.button>
        ) : (
          <>
            <Countdown endTime={wallet.rewardEndTime} variant="gold" hideDays />
            <div className="mt-4 h-1.5 rounded-full bg-space-600 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-gold-400 to-gold-500 transition-all"
                style={{
                  width: `${
                    100 -
                    Math.min(
                      100,
                      ((wallet.rewardEndTime - Date.now()) / (1000 * 60 * 60 * 24)) * 100,
                    )
                  }%`,
                }}
                key={tick}
              />
            </div>
          </>
        )}
      </motion.div>

      {/* Action Buttons */}
      <div className="mt-5 grid grid-cols-3 gap-3">
        <ActionButton
          onClick={() => setShowDeposit(true)}
          icon={<ArrowDownCircle size={18} />}
          label="Deposit"
          variant="teal-filled"
        />
        <ActionButton
          onClick={() => setShowWithdraw(true)}
          icon={<ArrowUpCircle size={18} />}
          label="Withdraw"
          variant="teal-outline"
        />
        <ActionButton
          onClick={onClaim}
          disabled={!rewardReady}
          icon={<Star size={18} />}
          label="Claim"
          variant="gold"
          badge={rewardReady}
        />
      </div>

      {/* Transactions */}
      <div className="mt-7">
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-base font-semibold">Recent Transactions</h2>
          <span className="text-xs text-gray-500">{wallet.transactions.length} total</span>
        </div>
        <div className="bg-space-700 border border-space-500 rounded-2xl divide-y divide-space-500 overflow-hidden">
          {loading ? (
            <>
              <TransactionSkeleton />
              <TransactionSkeleton />
              <TransactionSkeleton />
            </>
          ) : (
            <AnimatePresence initial={false}>
              {wallet.transactions.slice(0, 8).map((t) => (
                <motion.div
                  layout
                  key={t.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-3 px-4 py-3"
                >
                  <div
                    className={`h-10 w-10 rounded-full border grid place-items-center ${txTint(t.type)}`}
                  >
                    {txIcon(t.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-white truncate">{t.desc}</div>
                    <div className="text-[11px] text-gray-500">{t.date}</div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`font-mono font-bold text-sm ${
                        t.tokens > 0 ? 'text-emerald-300' : 'text-rose-300'
                      }`}
                    >
                      {t.tokens > 0 ? '+' : ''}
                      {t.tokens}
                    </div>
                    <div className="text-[11px] text-gray-500">{t.usdt.toFixed(2)} USDT</div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>

      <DepositModal open={showDeposit} onClose={() => setShowDeposit(false)} />
      <WithdrawModal open={showWithdraw} onClose={() => setShowWithdraw(false)} />
    </div>
  )
}

function ActionButton({ icon, label, variant, onClick, disabled, badge }) {
  const styles = {
    'teal-filled': 'bg-teal-500 hover:bg-teal-400 text-space-900 shadow-teal-glow',
    'teal-outline': 'bg-transparent border border-teal-400 text-teal-300 hover:bg-teal-500/10',
    gold: 'bg-gold-500 hover:bg-gold-400 text-amber-950 shadow-gold-glow',
  }
  return (
    <motion.button
      type="button"
      whileTap={{ scale: 0.96 }}
      disabled={disabled}
      onClick={onClick}
      className={`relative h-12 rounded-2xl flex items-center justify-center gap-1.5 font-semibold text-sm transition disabled:opacity-50 disabled:shadow-none ${
        styles[variant] || styles['teal-filled']
      }`}
    >
      {badge && (
        <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-rose-400 ring-2 ring-space-900 animate-pulse" />
      )}
      {icon}
      <span>{label}</span>
    </motion.button>
  )
}
