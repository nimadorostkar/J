// === FILE: tokenvault/src/api/auth.js ===
import { api, tokenStore } from './client.js'

export const authApi = {
  register: ({ firstName, lastName, email, password, inviteCode }) =>
    api.post(
      '/auth/register/',
      { firstName, lastName, email, password, inviteCode },
      { auth: false },
    ),

  login: ({ email, password }) =>
    api.post('/auth/login/', { email, password }, { auth: false }),

  logout: () => {
    const refreshToken = tokenStore.getRefresh()
    return api.post('/auth/logout/', { refreshToken })
  },

  refresh: (refreshToken) =>
    api.post('/auth/refresh/', { refreshToken }, { auth: false }),

  forgotPassword: (email) =>
    api.post('/auth/forgot-password/', { email }, { auth: false }),

  resetPassword: ({ token, newPassword }) =>
    api.post('/auth/reset-password/', { token, newPassword }, { auth: false }),

  verifyEmail: (token) =>
    api.post('/auth/verify-email/', { token }, { auth: false }),
}
