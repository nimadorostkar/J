// === FILE: tokenvault/src/api/users.js ===
import { api } from './client.js'

export const usersApi = {
  me: () => api.get('/users/me/'),

  updateMe: (patch) => api.patch('/users/me/', patch),

  uploadAvatar: (file) => {
    const fd = new FormData()
    fd.append('avatar', file)
    return api.post('/users/me/avatar/', fd)
  },

  changePassword: ({ currentPassword, newPassword }) =>
    api.post('/users/me/password/', { currentPassword, newPassword }),

  status: () => api.get('/users/me/status/'),
}
