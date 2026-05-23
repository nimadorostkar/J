// === FILE: tokenvault/src/api/support.js ===
import { api } from './client.js'

export const supportApi = {
  faqs: () => api.get('/support/faqs/', { auth: false }),
  tickets: () => api.get('/support/tickets/'),
  createTicket: ({ subject, category, body }) =>
    api.post('/support/tickets/', { subject, category, body }),
  ticket: (id) => api.get(`/support/tickets/${id}/`),
  replyTicket: (id, body) => api.post(`/support/tickets/${id}/`, { body }),
  chatSession: () => api.post('/support/chat/session/'),
}
