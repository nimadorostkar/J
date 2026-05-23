// === FILE: tokenvault/src/api/index.js ===
// Barrel re-export so consumers can `import { walletApi } from '../api'`
export { api, request, tokenStore, onAuthChange, logoutLocally, ApiError, BASE, backendOrigin, resolveMediaUrl } from './client.js'
export { authApi } from './auth.js'
export { usersApi } from './users.js'
export { walletApi } from './wallet.js'
export { rewardsApi } from './rewards.js'
export { referralsApi } from './referrals.js'
export { notificationsApi } from './notifications.js'
export { supportApi } from './support.js'
export { referenceApi } from './reference.js'
export { tournamentsApi, luckySpinApi, healthApi } from './misc.js'
