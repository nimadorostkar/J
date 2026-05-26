import { useEffect, useMemo, useState } from 'react'
import { Copy } from 'lucide-react'
import BottomSheet from './BottomSheet.jsx'
import Field from './Field.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useWallet } from '../context/WalletContext.jsx'
import { useT } from '../i18n/LanguageContext.jsx'
import { walletApi } from '../api'

// Backend uses 'TRC20' / 'ERC20' (no dash). UI shows nicer label.
const NETWORKS = [
  { value: 'TRC20', label: 'TRC-20' },
  { value: 'ERC20', label: 'ERC-20' },
]

export default function DepositModal({ open, onClose }) {
  const [network, setNetwork] = useState('TRC20')
  const [amount, setAmount] = useState('')
  const [txHash, setTxHash] = useState('')
  const [address, setAddress] = useState('')
  const [minimum, setMinimum] = useState(10)
  const [loadingAddr, setLoadingAddr] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const { showToast } = useToast()
  const { initDeposit, wallet } = useWallet()
  const t = useT()

  // Fetch deposit address when network changes (and modal is open)
  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoadingAddr(true)
    walletApi
      .depositAddress(network)
      .then((res) => {
        if (cancelled) return
        setAddress(res?.address || '')
        if (res?.minimum) setMinimum(Number(res.minimum))
      })
      .catch(() => { if (!cancelled) setAddress('') })
      .finally(() => { if (!cancelled) setLoadingAddr(false) })
    return () => { cancelled = true }
  }, [open, network])

  const usdt = Number(amount) || 0
  const coins = useMemo(() => {
    const rate = wallet?.conversionRate || 10
    return rate > 0 ? Math.floor(usdt / rate) : 0
  }, [usdt, wallet?.conversionRate])

  const copyAddr = async () => {
    try {
      await navigator.clipboard.writeText(address)
      showToast(t('deposit.addressCopied'), 'success')
    } catch {
      showToast(t('common.copyFailed'), 'error')
    }
  }

  const onConfirm = async () => {
    if (!usdt || usdt < minimum) {
      showToast(t('deposit.minError', { min: minimum }), 'error')
      return
    }
    setSubmitting(true)
    try {
      await initDeposit({ network, amountUsdt: String(usdt), txHash: txHash.trim() || undefined })
      showToast(t('deposit.submitted'), 'success')
      setAmount('')
      setTxHash('')
      onClose?.()
    } catch (e) {
      showToast(e?.message || t('deposit.failed'), 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <BottomSheet open={open} onClose={onClose} title={t('deposit.title')}>
      <div className="flex gap-2 bg-space-800 p-1 rounded-full mb-4">
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

      <Field
        label={t('deposit.enterAmount')}
        type="number"
        inputMode="decimal"
        suffix="USDT"
        placeholder="0.00"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />

      <div className="flex items-baseline justify-between mt-3 px-1 text-sm">
        <span className="text-gray-400">{t('deposit.youWillReceive')}</span>
        <span className="font-mono font-bold text-teal-300 text-base">{coins} {t('wallet.hCoins')}</span>
      </div>

      <div className="mt-5 bg-space-800 border border-space-500 rounded-2xl p-4">
        <div className="text-xs text-gray-400 mb-1.5">{t('deposit.address', { network })}</div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-white truncate flex-1">
            {loadingAddr ? t('common.loading') : address || '—'}
          </span>
          <button
            type="button"
            onClick={copyAddr}
            disabled={!address}
            className="text-teal-300 hover:text-teal-200 p-1 rounded-md disabled:opacity-40"
            aria-label={t('common.copy')}
          >
            <Copy size={16} />
          </button>
        </div>
        <div className="mt-4 flex justify-center">
          {address ? (
            <img
              src={walletApi.depositAddressQrUrl(network)}
              alt="QR"
              className="h-32 w-32 rounded-xl bg-white p-1"
            />
          ) : (
            <div className="h-32 w-32 rounded-xl bg-teal-500/15 border border-teal-400/30 flex items-center justify-center text-teal-300 font-mono text-sm">
              QR
            </div>
          )}
        </div>
      </div>

      <Field
        label={t('deposit.txHash')}
        placeholder="0x… or T…"
        value={txHash}
        onChange={(e) => setTxHash(e.target.value)}
      />

      <p className="text-xs text-gold-400 mt-3">
        {t('deposit.minimum', { min: minimum, coins: Math.floor(minimum / (wallet?.conversionRate || 10)) })}
      </p>

      <button
        type="button"
        disabled={submitting}
        onClick={onConfirm}
        className="w-full mt-5 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition active:scale-[0.98] disabled:opacity-60"
      >
        {submitting ? t('deposit.submitting') : t('deposit.confirm')}
      </button>
    </BottomSheet>
  )
}
