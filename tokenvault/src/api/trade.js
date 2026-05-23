// === FILE: tokenvault/src/api/trade.js ===
import { api } from './client.js'

export const tradeApi = {
  // Bot config + active session in one round-trip.
  root: () => api.get('/trade/'),
  activate: (botType) => api.post('/trade/activate/', { botType }),
  sessions: ({ cursor } = {}) => api.get('/trade/sessions/', { query: { cursor } }),
  session: (id) => api.get(`/trade/sessions/${id}/`),
}
