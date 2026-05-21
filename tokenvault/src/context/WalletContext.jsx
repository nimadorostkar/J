import { createContext, useCallback, useContext, useEffect, useState } from 'react'

const WalletContext = createContext(null)

const DEFAULT_TRANSACTIONS = [
  { id: 1, type: 'deposit', desc: 'USDT Deposit', tokens: 5, usdt: 50.0, date: '2024-01-20 14:32' },
  { id: 2, type: 'reward', desc: 'Cycle Reward', tokens: 2, usdt: 20.0, date: '2024-01-18 09:00' },
  { id: 3, type: 'withdraw', desc: 'Withdrawal', tokens: -3, usdt: 30.0, date: '2024-01-15 16:45' },
  { id: 4, type: 'deposit', desc: 'USDT Deposit', tokens: 10, usdt: 100.0, date: '2024-01-12 11:15' },
  { id: 5, type: 'reward', desc: 'Referral Bonus', tokens: 1, usdt: 10.0, date: '2024-01-10 18:20' },
  { id: 6, type: 'deposit', desc: 'USDT Deposit', tokens: 4, usdt: 40.0, date: '2024-01-08 08:42' },
  { id: 7, type: 'withdraw', desc: 'Withdrawal', tokens: -2, usdt: 20.0, date: '2024-01-05 13:55' },
  { id: 8, type: 'reward', desc: 'Cycle Reward', tokens: 3, usdt: 30.0, date: '2024-01-02 09:00' },
]

const STORAGE_KEY = 'tokenvault.wallet'

const DEFAULT_WALLET = {
  hCoins: 47,
  usdtBalance: 470.0,
  rewardActive: false,
  rewardEndTime: null,
  transactions: DEFAULT_TRANSACTIONS,
}

export function WalletProvider({ children }) {
  const [wallet, setWallet] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? { ...DEFAULT_WALLET, ...JSON.parse(raw) } : DEFAULT_WALLET
    } catch {
      return DEFAULT_WALLET
    }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(wallet))
  }, [wallet])

  const activateReward = useCallback(() => {
    setWallet((w) => ({
      ...w,
      rewardActive: true,
      rewardEndTime: Date.now() + 1000 * 60 * 60 * 24, // 24h cycle
    }))
  }, [])

  const claimReward = useCallback(() => {
    setWallet((w) => {
      const tokens = 2
      return {
        ...w,
        hCoins: w.hCoins + tokens,
        usdtBalance: w.usdtBalance + tokens * 10,
        rewardActive: false,
        rewardEndTime: null,
        transactions: [
          {
            id: Date.now(),
            type: 'reward',
            desc: 'Cycle Reward',
            tokens,
            usdt: tokens * 10,
            date: new Date().toISOString().slice(0, 16).replace('T', ' '),
          },
          ...w.transactions,
        ],
      }
    })
  }, [])

  const deposit = useCallback((usdtAmount) => {
    const tokens = Math.floor(usdtAmount / 10)
    if (tokens <= 0) return
    setWallet((w) => ({
      ...w,
      hCoins: w.hCoins + tokens,
      usdtBalance: w.usdtBalance + tokens * 10,
      transactions: [
        {
          id: Date.now(),
          type: 'deposit',
          desc: 'USDT Deposit',
          tokens,
          usdt: tokens * 10,
          date: new Date().toISOString().slice(0, 16).replace('T', ' '),
        },
        ...w.transactions,
      ],
    }))
  }, [])

  const withdraw = useCallback((tokens) => {
    if (tokens <= 0) return
    setWallet((w) => {
      if (tokens > w.hCoins) return w
      return {
        ...w,
        hCoins: w.hCoins - tokens,
        usdtBalance: w.usdtBalance - tokens * 10,
        transactions: [
          {
            id: Date.now(),
            type: 'withdraw',
            desc: 'Withdrawal',
            tokens: -tokens,
            usdt: tokens * 10,
            date: new Date().toISOString().slice(0, 16).replace('T', ' '),
          },
          ...w.transactions,
        ],
      }
    })
  }, [])

  return (
    <WalletContext.Provider
      value={{ wallet, activateReward, claimReward, deposit, withdraw }}
    >
      {children}
    </WalletContext.Provider>
  )
}

export const useWallet = () => useContext(WalletContext)
