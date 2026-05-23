// === FILE: tokenvault/src/api/referrals.js ===
import { api } from './client.js'

export const referralsApi = {
  code: () => api.get('/referrals/code/'),
  network: () => api.get('/referrals/network/'),
  stats: () => api.get('/referrals/stats/'),
  milestones: () => api.get('/referrals/milestones/'),
  validate: (code) => api.post('/referrals/validate/', { code }, { auth: false }),
}
