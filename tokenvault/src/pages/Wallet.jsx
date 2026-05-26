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
  Trophy,
  Dices,
} from 'lucide-react'
import { useWallet } from '../context/WalletContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import Countdown from '../components/Countdown.jsx'
import CountUp from '../components/CountUp.jsx'
import { TransactionSkeleton } from '../components/Skeleton.jsx'
import DepositModal from '../components/DepositModal.jsx'
import WithdrawModal from '../components/WithdrawModal.jsx'
import { notificationsApi } from '../api'

function txIcon(type) {
  if (type === 'deposit') return <ArrowUp size={16} className="text-emerald-400" />
  if (type === 'withdraw' || type === 'bot_fee')
    return <ArrowDown size={16} className="text-rose-400" />
  if (type === 'bot_profit')
    return <ArrowUp size={16} className="text-teal-300" />
  // reward / commission / referral_milestone — fall through
  return <Star size={16} className="text-gold-400" />
}

function txTint(type) {
  if (type === 'deposit') return 'bg-emerald-500/15 border-emerald-400/30'
  if (type === 'withdraw' || type === 'bot_fee')
    return 'bg-rose-500/15 border-rose-400/30'
  if (type === 'bot_profit')
    return 'bg-teal-500/15 border-teal-400/30'
  return 'bg-gold-500/15 border-gold-400/30'
}

export default function WalletPage() {
  const { wallet, loading, activateReward, claimReward } = useWallet()
  const { showToast } = useToast()
  const t = useT()
  const [showDeposit, setShowDeposit] = useState(false)
  const [showWithdraw, setShowWithdraw] = useState(false)
  const [tick, setTick] = useState(0)
  const [busy, setBusy] = useState(false)
  const [unread, setUnread] = useState(0)

  useEffect(() => {
    let cancelled = false
    notificationsApi.unreadCount().then((r) => { if (!cancelled) setUnread(r?.unread || 0) }).catch(() => {})
    const id = setInterval(() => {
      notificationsApi.unreadCount().then((r) => { if (!cancelled) setUnread(r?.unread || 0) }).catch(() => {})
    }, 30_000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (!wallet.rewardActive) return
    const id = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [wallet.rewardActive])

  const rewardReady =
    wallet.rewardActive && wallet.rewardEndTime && wallet.rewardEndTime <= Date.now()

  // === Reward cycle copy + progress ===
  // Default to 15 days × 20% so the card has labels even before /reward/cycle
  // returns. Once the cycle (or no-cycle preview) loads, prefer the live values.
  const cycle = wallet.cycle || {}
  const FIFTEEN_DAYS_MS = 15 * 24 * 3600 * 1000
  const cycleDurationMs = Number(cycle.durationMs) || FIFTEEN_DAYS_MS
  const rewardDurationDays = Math.round(cycleDurationMs / (24 * 3600 * 1000))
  const rewardPercent = Number(cycle.rewardPercent) || 20
  const rewardTokens = Number(cycle.rewardTokens || 0)
  const rewardAmountLabel = rewardTokens
    ? rewardTokens.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : ''
  const rewardProgressPct = wallet.rewardEndTime
    ? Math.max(
        0,
        Math.min(
          100,
          ((cycleDurationMs - (wallet.rewardEndTime - Date.now())) / cycleDurationMs) * 100,
        ),
      )
    : 0

  // === Activation eligibility ===
  // Backend tells us whether the user can activate AND why not (each
  // reason is { code, message }). Multiple reasons can fire at once.
  const canActivate = cycle.canActivate !== false  // default true so older clients still see button enabled
  const ineligibilityReasons = Array.isArray(cycle.ineligibilityReasons)
    ? cycle.ineligibilityReasons
    : []

  const onActivate = async () => {
    setBusy(true)
    try {
      await activateReward()
      showToast(t('wallet.activated'), 'success')
    } catch (e) {
      // Backend may return multiple reasons (e.g. balance AND no referral).
      const reasons = e?.data?.reasons
      if (Array.isArray(reasons) && reasons.length) {
        reasons.forEach((r) => showToast(r.message, 'error'))
      } else {
        showToast(e?.message || t('wallet.couldNotActivate'), 'error')
      }
    } finally { setBusy(false) }
  }

  const onClaim = async () => {
    setBusy(true)
    try {
      await claimReward()
      showToast(t('wallet.claimed'), 'success')
    } catch (e) {
      showToast(e?.message || t('wallet.claimFailed'), 'error')
    } finally { setBusy(false) }
  }

  return (
    <div className="relative w-full max-w-[480px] mx-auto px-5 pt-6 pb-28 bg-space-900 min-h-[100dvh]">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold">{t('wallet.title')}</h1>
        <button
          type="button"
          aria-label={t('wallet.notifications')}
          onClick={async () => {
            try {
              await notificationsApi.markAllRead()
              setUnread(0)
              showToast(t('wallet.markedAllRead'), 'success')
            } catch (e) { showToast(e?.message || t('wallet.couldNotUpdate'), 'error') }
          }}
          className="relative h-10 w-10 grid place-items-center rounded-full border border-space-500 bg-space-700 hover:border-teal-400 transition"
        >
          <Bell size={18} className="text-gray-300" />
          {unread > 0 && (
            <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-rose-500 text-white text-[10px] font-bold grid place-items-center ring-2 ring-space-900">
              {unread > 99 ? '99+' : unread}
            </span>
          )}
        </button>
      </div>

      {/* Balance Card */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="rounded-3xl border border-teal-400/40 bg-gradient-to-br from-teal-500/10 to-space-700 p-5 shadow-teal-glow"
      >
        <div className="text-xs text-gray-400 uppercase tracking-wider">{t('wallet.totalBalance')}</div>
        <div className="flex items-center gap-3 mt-2">
          <div className="h-11 w-11 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 grid place-items-center shadow-gold-glow">
            <Coins size={22} className="text-amber-900" strokeWidth={2.5} />
          </div>
          <div className="font-mono font-bold text-[36px] leading-none">
            <CountUp to={wallet.hCoins} /> <span className="text-white">{t('wallet.hCoins')}</span>
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
        className="mt-3 rounded-2xl border border-gold-400/40 bg-gradient-to-br from-gold-500/10 to-space-700 p-3.5"
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <Gift size={13} className="text-gold-400" />
            <span className="text-[11px] font-semibold text-gold-300 uppercase tracking-wider">{t('wallet.nextReward')}</span>
          </div>
          {rewardAmountLabel && (
            <span className="font-mono text-[12px] font-bold text-gold-300">
              +{rewardAmountLabel} H
            </span>
          )}
        </div>

        {!wallet.rewardActive ? (
          <>
            <p className="text-[11px] text-gray-400 mb-2 leading-snug">
              {t('wallet.earnPercent', { percent: rewardPercent, days: rewardDurationDays })}
            </p>

            {/* Pre-activation requirement list — only shown if any reason is failing. */}
            {!canActivate && ineligibilityReasons.length > 0 && (
              <ul className="mb-2.5 space-y-1">
                {ineligibilityReasons.map((r) => (
                  <li
                    key={r.code}
                    className="flex items-start gap-1.5 text-[11px] text-rose-300 leading-snug"
                  >
                    <span className="mt-[1px] shrink-0">⚠</span>
                    <span>{r.message}</span>
                  </li>
                ))}
              </ul>
            )}

            <button
              type="button"
              onClick={onActivate}
              disabled={busy || !canActivate}
              title={!canActivate ? ineligibilityReasons.map((r) => r.message).join(' ') : undefined}
              className="w-full h-9 rounded-full bg-gold-500 hover:bg-gold-400 text-amber-950 font-semibold text-sm shadow-gold-glow active:scale-[0.98] transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {busy ? t('wallet.activating') : t('wallet.activateCycle')}
            </button>
          </>
        ) : rewardReady ? (
          <motion.button
            type="button"
            onClick={onClaim}
            disabled={busy}
            animate={{ scale: [1, 1.03, 1] }}
            transition={{ duration: 1.4, repeat: Infinity }}
            className="w-full h-9 rounded-full bg-gold-500 text-amber-950 font-semibold text-sm shadow-gold-glow disabled:opacity-60"
          >
            {busy ? t('wallet.claiming') : t('wallet.claimAmount', { amount: rewardAmountLabel || '' })}
          </motion.button>
        ) : (
          <>
            <Countdown endTime={wallet.rewardEndTime} variant="gold" compact />
            <div className="mt-2.5 h-1 rounded-full bg-space-600 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-gold-400 to-gold-500 transition-all"
                style={{ width: `${rewardProgressPct}%` }}
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
          label={t('wallet.deposit')}
          variant="teal-filled"
        />
        <ActionButton
          onClick={() => setShowWithdraw(true)}
          icon={<ArrowUpCircle size={18} />}
          label={t('wallet.withdraw')}
          variant="teal-outline"
        />
        <ActionButton
          onClick={onClaim}
          disabled={!rewardReady}
          icon={<Star size={18} />}
          label={t('wallet.claim')}
          variant="gold"
          badge={rewardReady}
        />
      </div>

      {/* Coming Soon: Tournaments & Lucky Spin */}
      <div className="mt-5 grid grid-cols-2 gap-3">
        <ComingSoonCard
          label={t('wallet.tournaments')}
          comingSoon={t('wallet.comingSoon')}
          icon={<Trophy size={28} className="text-amber-300" />}
          tint="bg-amber-500/15"
          border="border-amber-400/30"
          accent="from-transparent via-amber-400/60 to-transparent"
        />
        <ComingSoonCard
          label={t('wallet.luckySpin')}
          comingSoon={t('wallet.comingSoon')}
          icon={<Dices size={28} className="text-purple-300" />}
          tint="bg-purple-500/15"
          border="border-purple-400/30"
          accent="from-transparent via-purple-400/60 to-transparent"
        />
      </div>

      {/* Transactions */}
      <div className="mt-7">
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-base font-semibold">{t('wallet.recentTransactions')}</h2>
          <span className="text-xs text-gray-500">{t('wallet.totalCount', { count: wallet.transactions.length })}</span>
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

function ComingSoonCard({ label, comingSoon, icon, tint, border, accent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className={`relative rounded-2xl ${tint} backdrop-blur-md border ${border} px-3 pt-4 pb-3 flex flex-col items-center gap-2 overflow-hidden`}
    >
      <div className={`absolute top-0 left-0 right-0 h-px bg-gradient-to-r ${accent}`} />
      {icon}
      <span className="text-[13.5px] font-semibold text-white">{label}</span>
      <span className="text-[9.5px] font-bold tracking-[0.12em] uppercase text-white/55 px-3 py-1 rounded-full bg-black/25 border border-white/15">
        {comingSoon}
      </span>
    </motion.div>
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
