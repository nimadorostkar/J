import { useEffect, useState } from 'react'
import { Minus, Plus } from 'lucide-react'
import BottomSheet from './BottomSheet.jsx'
import Field from './Field.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useWallet } from '../context/WalletContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import { walletApi } from '../api'

const NETWORKS = [
  { value: 'TRC20', label: 'TRC-20' },
  { value: 'ERC20', label: 'ERC-20' },
]

export default function WithdrawModal({ open, onClose }) {
  const [tokens, setTokens] = useState(1)
  const [network, setNetwork] = useState('TRC20')
  const [address, setAddress] = useState('')
  const [fee, setFee] = useState(1)
  const [submitting, setSubmitting] = useState(false)
  const [eligibility, setEligibility] = useState(null)
  const { showToast } = useToast()
  const { wallet, initWithdraw } = useWallet()
  const t = useT()

  const conversion = Number(wallet?.conversionRate || 10)
  const usdtEquiv = tokens * conversion
  const receivable = Math.max(0, usdtEquiv - fee)

  // Load networks (fee/min) + eligibility when opened
  useEffect(() => {
    if (!open) return
    let cancelled = false
    walletApi.networks().then((nets) => {
      if (cancelled) return
      const cur = nets.find((n) => n.id === network)
      if (cur?.fee) setFee(Number(cur.fee))
    }).catch(() => {})
    walletApi.withdrawEligibility().then((e) => {
      if (!cancelled) setEligibility(e)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [open, network])

  const onConfirm = async () => {
    if (tokens < 1) return showToast(t('withdraw.atLeastOne'), 'error')
    if (tokens > (wallet?.hCoins || 0)) return showToast(t('withdraw.insufficient'), 'error')
    if (!address || address.length < 10) return showToast(t('withdraw.validAddress'), 'error')
    setSubmitting(true)
    try {
      await initWithdraw({ network, address: address.trim(), tokens: String(tokens) })
      showToast(t('withdraw.submitted', { amount: tokens }), 'success')
      setTokens(1)
      setAddress('')
      onClose?.()
    } catch (e) {
      showToast(e?.message || t('withdraw.failed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const canWithdraw = eligibility?.eligible !== false

  return (
    <BottomSheet open={open} onClose={onClose} title={t('withdraw.title')}>
      {eligibility && !eligibility.eligible && (
        <div className="mb-3 rounded-xl border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-amber-200 text-xs">
          {eligibility.reason || t('withdraw.locked')}
        </div>
      )}

      <div className="bg-space-800 border border-space-500 rounded-2xl p-4 mb-4">
        <div className="text-xs text-gray-400 mb-3">{t('withdraw.numberTokens')}</div>
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setTokens((n) => Math.max(1, n - 1))}
            className="h-11 w-11 rounded-full bg-space-600 border border-space-500 flex items-center justify-center text-white hover:border-teal-400 transition active:scale-95"
            aria-label={t('withdraw.decrease')}
          >
            <Minus size={18} />
          </button>
          <div className="text-center">
            <div className="font-mono text-3xl font-bold">{tokens}</div>
            <div className="text-xs text-gray-400 mt-1">= {usdtEquiv} USDT</div>
          </div>
          <button
            type="button"
            onClick={() => setTokens((n) => Math.min(Math.floor(wallet?.hCoins || 0), n + 1))}
            className="h-11 w-11 rounded-full bg-space-600 border border-space-500 flex items-center justify-center text-white hover:border-teal-400 transition active:scale-95"
            aria-label={t('withdraw.increase')}
          >
            <Plus size={18} />
          </button>
        </div>
      </div>

      <Field
        label={t('withdraw.destination')}
        placeholder={t('withdraw.pasteAddress')}
        value={address}
        onChange={(e) => setAddress(e.target.value)}
      />

      <div className="flex gap-2 bg-space-800 p-1 rounded-full mt-4">
        {NETWORKS.map((n) => (
          <button
            key={n.value}
            type="button"
            onClick={() => setNetwork(n.value)}
            className={`flex-1 h-9 rounded-full text-sm font-medium transition ${
              network === n.value
                ? 'bg-teal-500 text-space-900 shadow-teal-glow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {n.label}
          </button>
        ))}
      </div>

      <div className="mt-4 text-xs text-gray-400">{t('withdraw.networkFee', { fee })}</div>
      <div className="mt-1 flex items-baseline justify-between">
        <span className="text-sm text-gray-300">{t('withdraw.totalReceivable')}</span>
        <span className="font-mono font-bold text-teal-300 text-base">{receivable.toFixed(2)} USDT</span>
      </div>

      <button
        type="button"
        disabled={submitting || !canWithdraw}
        onClick={onConfirm}
        className="w-full mt-5 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition active:scale-[0.98] disabled:opacity-50"
      >
        {submitting ? t('withdraw.submitting') : t('withdraw.confirm')}
      </button>
    </BottomSheet>
  )
}
