// === FILE: tokenvault/src/api/rewards.js ===
import { api } from './client.js'

export const rewardsApi = {
  cycle: () => api.get('/reward/cycle/'),
  activate: () => api.post('/reward/cycle/activate/'),
  claim: (idempotencyKey) =>
    api.post(
      '/reward/cycle/claim/',
      null,
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined,
    ),
  globalCycle: () => api.get('/reward/global-cycle/'),
}
