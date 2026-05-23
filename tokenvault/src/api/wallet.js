// === FILE: tokenvault/src/api/wallet.js ===
import { api, BASE } from './client.js'

export const walletApi = {
  get: () => api.get('/wallet/'),

  transactions: ({ type, cursor } = {}) =>
    api.get('/wallet/transactions/', { query: { type, cursor } }),

  networks: () => api.get('/wallet/networks/'),

  depositAddress: (network = 'TRC20') =>
    api.get('/wallet/deposit-address/', { query: { network } }),

  depositAddressQrUrl: (network = 'TRC20') =>
    `${BASE}/wallet/deposit-address/qr/?network=${encodeURIComponent(network)}`,

  initDeposit: ({ network, amountUsdt, txHash, idempotencyKey }) =>
    api.post(
      '/wallet/deposit/',
      { network, amountUsdt, txHash },
      idempotencyKey
        ? { headers: { 'Idempotency-Key': idempotencyKey } }
        : undefined,
    ),

  depositStatus: (txId) => api.get(`/wallet/deposit/${txId}/`),

  initWithdraw: ({ network, address, tokens, idempotencyKey }) =>
    api.post(
      '/wallet/withdraw/',
      { network, address, tokens },
      idempotencyKey
        ? { headers: { 'Idempotency-Key': idempotencyKey } }
        : undefined,
    ),

  withdrawEligibility: () => api.get('/wallet/withdraw/eligibility/'),

  withdrawStatus: (txId) => api.get(`/wallet/withdraw/${txId}/`),
}
