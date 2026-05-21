import { useState } from 'react'
import { Minus, Plus } from 'lucide-react'
import BottomSheet from './BottomSheet.jsx'
import Field from './Field.jsx'
import { useToast } from '../context/ToastContext.jsx'
import { useWallet } from '../context/WalletContext.jsx'

const FEE = 1

export default function WithdrawModal({ open, onClose }) {
  const [tokens, setTokens] = useState(1)
  const [network, setNetwork] = useState('TRC-20')
  const [address, setAddress] = useState('')
  const { showToast } = useToast()
  const { wallet, withdraw } = useWallet()

  const usdtEquiv = tokens * 10
  const receivable = Math.max(0, usdtEquiv - FEE)

  const onConfirm = () => {
    if (tokens < 1) return showToast('Withdraw at least 1 token', 'error')
    if (tokens > wallet.hCoins) return showToast('Insufficient balance', 'error')
    if (!/^[A-Za-z0-9]{20,}$/.test(address)) return showToast('Enter a valid wallet address', 'error')
    withdraw(tokens)
    showToast(`Withdrew ${tokens} H Coins`, 'success')
    setTokens(1)
    setAddress('')
    onClose?.()
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Withdraw">
      <div className="bg-space-800 border border-space-500 rounded-2xl p-4 mb-4">
        <div className="text-xs text-gray-400 mb-3">Number of tokens</div>
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setTokens((t) => Math.max(1, t - 1))}
            className="h-11 w-11 rounded-full bg-space-600 border border-space-500 flex items-center justify-center text-white hover:border-teal-400 transition active:scale-95"
            aria-label="Decrease"
          >
            <Minus size={18} />
          </button>
          <div className="text-center">
            <div className="font-mono text-3xl font-bold">{tokens}</div>
            <div className="text-xs text-gray-400 mt-1">= {usdtEquiv} USDT</div>
          </div>
          <button
            type="button"
            onClick={() => setTokens((t) => Math.min(wallet.hCoins, t + 1))}
            className="h-11 w-11 rounded-full bg-space-600 border border-space-500 flex items-center justify-center text-white hover:border-teal-400 transition active:scale-95"
            aria-label="Increase"
          >
            <Plus size={18} />
          </button>
        </div>
      </div>

      <Field
        label="Destination Wallet Address"
        placeholder="Paste address"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
      />

      <div className="flex gap-2 bg-space-800 p-1 rounded-full mt-4">
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

      <div className="mt-4 text-xs text-gray-400">Network fee: {FEE} USDT</div>
      <div className="mt-1 flex items-baseline justify-between">
        <span className="text-sm text-gray-300">Total receivable</span>
        <span className="font-mono font-bold text-teal-300 text-base">{receivable.toFixed(2)} USDT</span>
      </div>

      <button
        type="button"
        onClick={onConfirm}
        className="w-full mt-5 h-12 rounded-full bg-teal-500 hover:bg-teal-400 text-space-900 font-semibold shadow-teal-glow transition active:scale-[0.98]"
      >
        Confirm Withdrawal
      </button>
    </BottomSheet>
  )
}
