import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { walletApi, rewardsApi } from '../api'
import { useAuth } from './AuthContext.jsx'

const WalletContext = createContext(null)

// Types that REMOVE H Coins from the balance — shown as negative in the UI.
const DEBIT_TYPES = new Set(['withdraw', 'bot_fee'])

// Human-readable labels per transaction type.
const TYPE_LABELS = {
  deposit: 'USDT Deposit',
  withdraw: 'Withdrawal',
  reward: 'Cycle Reward',
  commission: 'Referral Bonus',
  referral_milestone: 'Referral Milestone',
  bot_fee: 'Bot Activation Fee',
  bot_profit: 'Bot Profit',
}

// Normalize a backend transaction (TransactionSerializer) to what the UI wants.
function normalizeTransaction(t) {
  // Backend emits snake_case: id, type, amount_hcoin, amount_usdt, status, created_at...
  const amountH = Number(t.amount_hcoin ?? t.amountHcoin ?? 0)
  const amountU = Number(t.amount_usdt ?? t.amountUsdt ?? 0)
  const type = t.type || 'reward'
  const signed = DEBIT_TYPES.has(type) ? -Math.abs(amountH) : Math.abs(amountH)
  const desc = TYPE_LABELS[type] || 'Cycle Reward'
  const d = new Date(t.created_at || t.createdAt || t.date || Date.now())
  return {
    id: t.id,
    type,
    desc,
    tokens: signed,
    usdt: amountU,
    date: d.toISOString().slice(0, 16).replace('T', ' '),
    status: t.status,
    network: t.network,
    raw: t,
  }
}

const EMPTY_WALLET = {
  hCoins: 0,
  usdtBalance: 0,
  usdtEquivalent: 0,
  conversionRate: 10,
  rewardActive: false,
  rewardEndTime: null,
  rewardDurationHours: 12,
  hasDeposit: false,
  hasReferral: false,
  transactions: [],
  cycle: null,
  // platform/global cycle
  globalCycleEnd: null,
}

export function WalletProvider({ children }) {
  const { user } = useAuth()
  const [wallet, setWallet] = useState(EMPTY_WALLET)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Helper to fetch /wallet + /reward/cycle + /wallet/transactions in parallel
  const reload = useCallback(async () => {
    if (!user) return
    setLoading(true)
    setError(null)
    try {
      const [w, tx, cycle, gc] = await Promise.allSettled([
        walletApi.get(),
        walletApi.transactions(),
        rewardsApi.cycle(),
        rewardsApi.globalCycle(),
      ])

      setWallet((prev) => {
        const next = { ...prev }
        if (w.status === 'fulfilled' && w.value) {
          const v = w.value
          next.hCoins = Number(v.hCoins ?? 0)
          next.usdtBalance = Number(v.usdtBalance ?? 0)
          next.usdtEquivalent = Number(v.usdtEquivalent ?? 0)
          next.conversionRate = Number(v.conversionRate ?? 10)
          next.rewardActive = Boolean(v.rewardActive)
          next.rewardEndTime = v.rewardEndTime ? new Date(v.rewardEndTime).getTime() : null
          next.rewardDurationHours = Number(v.rewardDurationHours ?? 12)
          next.hasDeposit = Boolean(v.hasDeposit)
          next.hasReferral = Boolean(v.hasReferral)
        }
        if (tx.status === 'fulfilled' && tx.value) {
          const rows = Array.isArray(tx.value) ? tx.value : tx.value.results || []
          next.transactions = rows.map(normalizeTransaction)
        }
        if (cycle.status === 'fulfilled' && cycle.value) {
          next.cycle = cycle.value
          if (cycle.value.endTime) {
            next.rewardEndTime = new Date(cycle.value.endTime).getTime()
          }
          if (typeof cycle.value.active === 'boolean') {
            next.rewardActive = cycle.value.active
          }
        }
        if (gc.status === 'fulfilled' && gc.value && gc.value.endTime) {
          next.globalCycleEnd = new Date(gc.value.endTime).getTime()
        }
        return next
      })
    } catch (e) {
      setError(e?.message || 'Failed to load wallet')
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => {
    if (user) reload()
    else setWallet(EMPTY_WALLET)
  }, [user, reload])

  const activateReward = useCallback(async () => {
    const c = await rewardsApi.activate()
    setWallet((w) => ({
      ...w,
      rewardActive: true,
      rewardEndTime: c?.endTime ? new Date(c.endTime).getTime() : w.rewardEndTime,
      cycle: c,
    }))
    return c
  }, [])

  const claimReward = useCallback(async () => {
    const idem = `claim-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const res = await rewardsApi.claim(idem)
    // Refresh balances + tx list
    await reload()
    return res
  }, [reload])

  const initDeposit = useCallback(async (payload) => {
    const idem = `dep-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const tx = await walletApi.initDeposit({ ...payload, idempotencyKey: idem })
    await reload()
    return tx
  }, [reload])

  const initWithdraw = useCallback(async (payload) => {
    const idem = `wd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const tx = await walletApi.initWithdraw({ ...payload, idempotencyKey: idem })
    await reload()
    return tx
  }, [reload])

  return (
    <WalletContext.Provider
      value={{
        wallet,
        loading,
        error,
        reload,
        activateReward,
        claimReward,
        initDeposit,
        initWithdraw,
      }}
    >
      {children}
    </WalletContext.Provider>
  )
}

export const useWallet = () => useContext(WalletContext)
