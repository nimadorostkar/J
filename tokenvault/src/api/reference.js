// === FILE: tokenvault/src/api/reference.js ===
import { api } from './client.js'

export const referenceApi = {
  countries: () => api.get('/reference/countries/', { auth: false }),
  dialCodes: () => api.get('/reference/dial-codes/', { auth: false }),
  config: () => api.get('/reference/config/', { auth: false }),
}
