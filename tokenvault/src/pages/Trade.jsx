import { useCallback, useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Bell, Bot, Sparkles, TrendingUp, Clock, CheckCircle2 } from 'lucide-react'
import { tradeApi } from '../api'
import { useWallet } from '../context/WalletContext.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import Countdown from '../components/Countdown.jsx'
import CountUp from '../components/CountUp.jsx'
import { Coins } from 'lucide-react'

/* ── helpers ────────────────────────────────────────────────────────── */

function formatHcoin(v, digits = 4) {
  if (v == null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function formatDuration(seconds) {
  if (!seconds) return '—'
  if (seconds >= 86400) {
    const days = Math.round(seconds / 86400)
    return `${days} day${days === 1 ? '' : 's'}`
  }
  if (seconds >= 3600) {
    const hrs = Math.round(seconds / 3600)
    return `${hrs} hour${hrs === 1 ? '' : 's'}`
  }
  return `${Math.round(seconds / 60)} min`
}

function botVariant(type) {
  return type === 'expert'
    ? {
        ring: 'border-purple-400/50',
        bg: 'from-purple-500/15 to-space-700',
        accent: 'text-purple-300',
        button: 'bg-purple-500 hover:bg-purple-400 text-white shadow-[0_0_20px_rgba(168,85,247,0.4)]',
        Icon: Sparkles,
      }
    : {
        ring: 'border-teal-400/50',
        bg: 'from-teal-500/15 to-space-700',
        accent: 'text-teal-300',
        button: 'bg-teal-500 hover:bg-teal-400 text-space-900 shadow-teal-glow',
        Icon: Bot,
      }
}

/* ── page ───────────────────────────────────────────────────────────── */

export default function Trade() {
  const { wallet, reload: reloadWallet } = useWallet()
  const { showToast } = useToast()
  const t = useT()

  const [bots, setBots] = useState(null)        // { basic: {...}, expert: {...} }
  const [active, setActive] = useState(null)    // BotSession | null
  const [sessions, setSessions] = useState([])  // recent history
  const [loading, setLoading] = useState(true)
  const [activating, setActivating] = useState(null) // 'basic' | 'expert' | null

  // Fetch config + active + recent history
  const refresh = useCallback(async () => {
    try {
      const [root, list] = await Promise.allSettled([
        tradeApi.root(),
        tradeApi.sessions(),
      ])
      if (root.status === 'fulfilled') {
        setBots(root.value?.bots || null)
        setActive(root.value?.active || null)
      }
      if (list.status === 'fulfilled') {
        const rows = Array.isArray(list.value)
          ? list.value
          : list.value?.results || []
        setSessions(rows)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  // On mount: refresh trade data AND pull the latest wallet so the
  // balance card here matches the Wallet page exactly.
  useEffect(() => {
    refresh()
    reloadWallet?.()
  }, [refresh, reloadWallet])

  // Poll every 30s when a bot is active so completion + history update
  // even without a WebSocket round trip.
  useEffect(() => {
    if (!active) return
    const id = setInterval(refresh, 30_000)
    return () => clearInterval(id)
  }, [active, refresh])

  const onActivate = async (botType) => {
    if (active) {
      showToast(t('trade.anotherRunningToast'), 'error')
      return
    }
    setActivating(botType)
    try {
      const session = await tradeApi.activate(botType)
      setActive(session)
      await reloadWallet()
      await refresh()
      showToast(t('trade.activatedToast'), 'success')
    } catch (e) {
      showToast(e?.message || t('trade.activationFailed'), 'error')
    } finally {
      setActivating(null)
    }
  }

  /* ── derived values ─────────────────────────────────────────────── */

  const balance = Number(wallet?.hCoins || 0)
  const previewFee = (cfg) =>
    cfg ? (balance * Number(cfg.feePercent || 0)) / 100 : 0
  const previewProfit = (cfg) => {
    if (!cfg) return [0, 0]
    return [
      (balance * Number(cfg.profitMinPercent || 0)) / 100,
      (balance * Number(cfg.profitMaxPercent || 0)) / 100,
    ]
  }

  return (
    <div className="relative w-full max-w-[480px] mx-auto px-5 pt-6 pb-28 bg-space-900 min-h-[100dvh]">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-2xl font-bold">{t('trade.title')}</h1>
        <span className="h-10 w-10 grid place-items-center rounded-full border border-space-500 bg-space-700">
          <Bell size={18} className="text-gray-300" />
        </span>
      </div>

      {/* Balance card — identical layout to the Wallet page so the two
          screens always show the same number in the same shape. */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="rounded-3xl border border-teal-400/40 bg-gradient-to-br from-teal-500/10 to-space-700 p-5 shadow-teal-glow"
      >
        <div className="text-xs text-gray-400 uppercase tracking-wider">{t('trade.availableBalance')}</div>
        <div className="flex items-center gap-3 mt-2">
          <div className="h-11 w-11 rounded-full bg-gradient-to-br from-gold-300 to-gold-500 grid place-items-center shadow-gold-glow">
            <Coins size={22} className="text-amber-900" strokeWidth={2.5} />
          </div>
          <div className="font-mono font-bold text-[36px] leading-none">
            <CountUp to={wallet?.hCoins || 0} maxDecimals={4} /> <span className="text-white">{t('wallet.hCoins')}</span>
          </div>
        </div>
        <div className="text-gray-400 text-[15px] mt-2">
          ≈ <CountUp to={wallet?.usdtEquivalent || 0} decimals={2} /> USDT
        </div>
      </motion.div>

      {/* Active bot card */}
      {active && (
        <ActiveBotCard
          session={active}
          onComplete={async () => { await refresh(); await reloadWallet() }}
          t={t}
        />
      )}

      {/* Bot options */}
      <div className="mt-5 space-y-3">
        {bots && [bots.basic, bots.expert].map((cfg) => {
          if (!cfg) return null
          const [pMin, pMax] = previewProfit(cfg)
          const fee = previewFee(cfg)
          const disabled = !!active || activating === cfg.type || balance <= 0
          const reason = active
            ? t('trade.anotherRunning')
            : balance <= 0
              ? t('trade.depositFirst')
              : null
          return (
            <BotCard
              key={cfg.type}
              cfg={cfg}
              fee={fee}
              previewMin={pMin}
              previewMax={pMax}
              disabled={disabled}
              disabledReason={reason}
              busy={activating === cfg.type}
              onActivate={() => onActivate(cfg.type)}
              t={t}
            />
          )
        })}
      </div>

      {/* History */}
      <div className="mt-7">
        <div className="flex items-center justify-between mb-3 px-1">
          <h2 className="text-base font-semibold">{t('trade.botHistory')}</h2>
          {sessions.length > 0 && (
            <span className="text-xs text-gray-500">
              {sessions.length === 1
                ? t('trade.sessionsOne', { count: sessions.length })
                : t('trade.sessionsMany', { count: sessions.length })}
            </span>
          )}
        </div>
        <div className="bg-space-700 border border-space-500 rounded-2xl overflow-hidden divide-y divide-space-500">
          {loading ? (
            <div className="px-4 py-6 text-center text-xs text-gray-500">{t('common.loading')}</div>
          ) : sessions.length === 0 ? (
            <div className="px-4 py-6 text-center text-xs text-gray-500">
              {t('trade.noBotYet')}
            </div>
          ) : (
            sessions.map((s) => <SessionRow key={s.id} s={s} t={t} />)
          )}
        </div>
      </div>
    </div>
  )
}

/* ── components ─────────────────────────────────────────────────────── */

function BotCard({ cfg, fee, previewMin, previewMax, disabled, disabledReason, busy, onActivate, t }) {
  const v = botVariant(cfg.type)
  const Icon = v.Icon
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className={`rounded-2xl border ${v.ring} bg-gradient-to-br ${v.bg} p-4`}
    >
      <div className="flex items-center gap-3">
        <div className={`h-10 w-10 rounded-full bg-space-700 grid place-items-center ${v.accent}`}>
          <Icon size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-white">{cfg.label}</div>
          <div className="text-[11px] text-gray-400">
            {t('trade.cycleSubtitle', { duration: formatDuration(cfg.durationSeconds) })}
          </div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
        <div className="rounded-xl bg-space-800/60 border border-space-500 p-2.5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">{t('trade.activationFee')}</div>
          <div className="font-mono font-semibold text-rose-300 mt-0.5">
            -{formatHcoin(fee)} H <span className="text-gray-500">({cfg.feePercent}%)</span>
          </div>
        </div>
        <div className="rounded-xl bg-space-800/60 border border-space-500 p-2.5">
          <div className="text-[10px] text-gray-500 uppercase tracking-wider">{t('trade.estProfit')}</div>
          <div className={`font-mono font-semibold ${v.accent} mt-0.5`}>
            +{formatHcoin(previewMin)} – {formatHcoin(previewMax)} H
          </div>
        </div>
      </div>

      <button
        type="button"
        disabled={disabled}
        onClick={onActivate}
        title={disabledReason || undefined}
        className={`mt-3 w-full h-11 rounded-full font-semibold text-sm transition active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed ${v.button}`}
      >
        {busy ? t('trade.activatingDots') : disabled && disabledReason ? disabledReason : t('trade.activate', { label: cfg.label })}
      </button>
    </motion.div>
  )
}

function ActiveBotCard({ session, onComplete, t }) {
  const v = botVariant(session.botType)
  const Icon = v.Icon
  const endTime = useMemo(
    () => (session.completesAt ? new Date(session.completesAt).getTime() : null),
    [session.completesAt],
  )
  const ready = endTime && endTime <= Date.now()

  // When the countdown crosses zero, trigger a refresh so the parent
  // picks up the completion.
  useEffect(() => {
    if (!endTime) return
    const ms = endTime - Date.now()
    if (ms <= 0) {
      onComplete?.()
      return
    }
    const t = setTimeout(() => onComplete?.(), ms + 1500)
    return () => clearTimeout(t)
  }, [endTime, onComplete])

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`mt-4 rounded-2xl border ${v.ring} bg-gradient-to-br ${v.bg} p-4`}
    >
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className={v.accent} />
        <span className={`text-[11px] font-semibold ${v.accent} uppercase tracking-wider`}>
          {session.botLabel} · {t('trade.running')}
        </span>
        <span className="ml-auto text-[10px] text-gray-500">
          {t('trade.feePaid')} <span className="font-mono text-rose-300">{formatHcoin(session.feeAmountHcoin)} H</span>
        </span>
      </div>

      {ready ? (
        <div className="rounded-xl bg-emerald-500/15 border border-emerald-400/30 p-3 text-center text-sm text-emerald-300">
          {t('trade.finalizing')}
        </div>
      ) : (
        endTime && <Countdown endTime={endTime} variant={session.botType === 'expert' ? 'gold' : 'teal'} compact />
      )}

      <p className="mt-3 text-[11px] text-gray-400 text-center leading-snug">
        {t('trade.expected', {
          min: session.profitMinPercent,
          max: session.profitMaxPercent,
          balance: formatHcoin(session.balanceAtStartHcoin),
        })}
      </p>
    </motion.div>
  )
}

function SessionRow({ s, t }) {
  const isCompleted = s.status === 'completed'
  const isActive = s.status === 'active'
  const v = botVariant(s.botType)
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div className={`h-9 w-9 rounded-full border border-space-500 grid place-items-center ${v.accent}`}>
        {isCompleted ? <CheckCircle2 size={16} /> : isActive ? <Clock size={16} /> : <TrendingUp size={16} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-white truncate">{s.botLabel}</div>
        <div className="text-[11px] text-gray-500">
          {new Date(s.startedAt).toLocaleString()} · {s.status}
        </div>
      </div>
      <div className="text-right">
        <div className="text-[11px] text-rose-300 font-mono">
          -{formatHcoin(s.feeAmountHcoin)} H
        </div>
        <div className={`text-[12px] font-mono font-semibold ${
          s.profitAmountHcoin && Number(s.profitAmountHcoin) > 0 ? v.accent : 'text-gray-500'
        }`}>
          {s.profitAmountHcoin
            ? `+${formatHcoin(s.profitAmountHcoin)} H`
            : isActive ? t('trade.pending') : '—'}
        </div>
      </div>
    </div>
  )
}
