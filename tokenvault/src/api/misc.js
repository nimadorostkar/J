// === FILE: tokenvault/src/api/misc.js ===
import { api } from './client.js'

export const tournamentsApi = {
  root: () => api.get('/tournaments/'),
}

export const luckySpinApi = {
  root: () => api.get('/lucky-spin/'),
}

export const healthApi = {
  check: () => api.get('/health/', { auth: false }),
}
