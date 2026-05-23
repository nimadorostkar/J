// === FILE: tokenvault/src/api/notifications.js ===
import { api } from './client.js'

export const notificationsApi = {
  list: ({ cursor } = {}) =>
    api.get('/notifications/', { query: { cursor } }),
  unreadCount: () => api.get('/notifications/unread-count/'),
  markRead: (id) => api.patch(`/notifications/${id}/read/`),
  markAllRead: () => api.post('/notifications/read-all/'),
}
