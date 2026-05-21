import { useMemo, useState } from 'react'
import { Copy } from 'lucide-react'
import BottomSheet from './BottomSheet.jsx'
import Field from './Field.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useWallet } from '../context/WalletContext.jsx'

const MOCK_ADDRESSES = {
  'TRC-20': 'TXn8gkV4hYy7nP4cFmZ5g5jWqJ2YvK9ABc',
  'ERC-20': '0xA9c3F2EeC7c9D5d4F38eB1234aB56cD7891234ef',
}

export default function DepositModal({ open, onClose }) {
  const [network, setNetwork] = useState('TRC-20')
  const [amount, setAmount] = useState('')
  const { showToast } = useToast()
  const { deposit } = useWallet()

  const usdt = Number(amount) || 0
  const coins = useMemo(() => Math.floor(usdt / 10), [usdt])
  const address = MOCK_ADDRESSES[network]

  const copyAddr = async () => {
    try {
      await navigator.clipboard.writeText(address)
      showToast('Address copied', 'success')
    } catch {
      showToast('Copy failed', 'error')
    }
  }

  const onConfirm = () => {
    if (usdt < 10) {
      showToast('Minimum 10 USDT', 'error')
      return
    }
    deposit(usdt)
    showToast(`Deposited ${coins} H Coins`, 'success')
    setAmount('')
    onClose?.()
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Deposit USDT">
      <div className="flex gap-2 bg-space-800 p-1 rounded-full mb-4">
        {['TRC-20', 'ERC-20'].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => setNetwork(n)}
            className={`flex-1 h-9 rounded-full text-sm font-medium transition ${
              network === n
                ? 'bg-teal-500 text-space-900 shadow-teal-glow'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            {n}
          </button>
        ))}
      </div>

      <Field
        label="Enter USDT Amount"
        type="number"
        inputMode="decimal"
        suffix="USDT"
        placeholder="0.00"
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
      />

      <div className="flex items-baseline justify-between mt-3 px-1 text-sm">
        <span className="text-gray-400">You will receive</span>
        <span className="font-mono font-bold text-teal-300 text-base">{coins} H Coins</span>
      </div>

      <div className="mt-5 bg-space-800 border border-space-500 rounded-2xl p-4">
        <div className="text-xs text-gray-400 mb-1.5">Deposit Address ({network})</div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-white truncate flex-1">{address}</span>
          <button
            type="button"
            onClick={copyAddr}
            className="text-teal-300 hover:text-teal-200 p-1 rounded-md"
            aria-label="Copy address"
          >
            <Copy size={16} />
          </button>
        </div>
        <div className="mt-4 flex justify-center">
          <div className="h-32 w-32 rounded-xl bg-teal-500/15 border border-teal-400/30 flex items-center justify-center text-teal-300 font-mono text-sm">
            QR
          </div>
        </div>
      </div>

      <p className="text-xs text-gold-400 mt-3">Minimum: 10 USDT = 1 H Coin</p>

      <button
        type="button"
        onClick={onConfirm}
        className="w-full mt-5 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition active:scale-[0.98]"
      >
        Confirm Deposit
      </button>
    </BottomSheet>
  )
}
