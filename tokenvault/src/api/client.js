// === FILE: tokenvault/src/api/client.js ===
// Lightweight fetch wrapper with JWT auth, auto-refresh on 401, and typed errors.
// No external deps.

// Fallback points at the HTTPS-fronted production backend so the bundle
// keeps working if VITE_API_BASE_URL ever fails to load. Dev / local
// overrides this with http://localhost:8000/api/v1 via .env.
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, '') ||
  'https://houston.avro-cafe.ir/api/v1'

const ACCESS_KEY = 'tokenvault.accessToken'
const REFRESH_KEY = 'tokenvault.refreshToken'

export const tokenStore = {
  getAccess() {
    try { return localStorage.getItem(ACCESS_KEY) } catch { return null }
  },
  getRefresh() {
    try { return localStorage.getItem(REFRESH_KEY) } catch { return null }
  },
  set(access, refresh) {
    try {
      if (access) localStorage.setItem(ACCESS_KEY, access)
      if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
    } catch {}
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
    } catch {}
  },
}

// Listeners notified on auth-state change (logout / token refreshed).
const authListeners = new Set()
export function onAuthChange(cb) {
  authListeners.add(cb)
  return () => authListeners.delete(cb)
}
function emitAuthChange(event) {
  authListeners.forEach((cb) => {
    try { cb(event) } catch {}
  })
}

export class ApiError extends Error {
  constructor(status, code, message, data) {
    super(message || code || `HTTP ${status}`)
    this.status = status
    this.code = code
    this.data = data
  }
}

function buildUrl(path, query) {
  // Compose the path portion (no host needed for relative base URLs).
  const rawPath = path.startsWith('http')
    ? path
    : `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

  // For relative base URLs (e.g. "/api/v1") we can't use `new URL(rawPath)`
  // directly — the URL constructor needs an absolute URL or a base.
  // Use window.location.origin as the base in the browser; fall back to a
  // dummy origin server-side / in tests so URL parsing still works.
  const base =
    typeof window !== 'undefined' && window.location
      ? window.location.origin
      : 'http://localhost'
  const url = rawPath.startsWith('http') ? new URL(rawPath) : new URL(rawPath, base)

  if (query && typeof query === 'object') {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null || v === '') continue
      url.searchParams.set(k, String(v))
    }
  }

  // If the base URL was relative, return path + search only — that way the
  // browser keeps the request same-origin and the Vite proxy can pick it up.
  if (!BASE_URL.startsWith('http') && !rawPath.startsWith('http')) {
    return `${url.pathname}${url.search}`
  }
  return url.toString()
}

let refreshInflight = null

async function refreshAccessToken() {
  if (refreshInflight) return refreshInflight
  const refresh = tokenStore.getRefresh()
  if (!refresh) throw new ApiError(401, 'NO_REFRESH', 'No refresh token available')

  refreshInflight = (async () => {
    const res = await fetch(buildUrl('/auth/refresh/'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: refresh }),
    })
    if (!res.ok) {
      tokenStore.clear()
      emitAuthChange({ type: 'logout', reason: 'refresh_failed' })
      throw new ApiError(res.status, 'REFRESH_FAILED', 'Session expired')
    }
    const data = await res.json()
    tokenStore.set(data.accessToken, data.refreshToken)
    emitAuthChange({ type: 'refreshed' })
    return data.accessToken
  })()

  try {
    return await refreshInflight
  } finally {
    refreshInflight = null
  }
}

async function parseBody(res) {
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    try { return await res.json() } catch { return null }
  }
  if (ct.startsWith('text/')) {
    try { return await res.text() } catch { return null }
  }
  return null
}

/**
 * Core request fn.
 * @param {string} method
 * @param {string} path - path relative to BASE_URL, or absolute URL
 * @param {object} [opts]
 * @param {object|FormData} [opts.body]
 * @param {object} [opts.query]
 * @param {object} [opts.headers]
 * @param {boolean} [opts.auth=true] - attach Authorization header
 * @param {boolean} [opts.raw=false] - return Response instead of parsed body
 */
export async function request(method, path, opts = {}) {
  const { body, query, headers = {}, auth = true, raw = false } = opts
  const url = buildUrl(path, query)
  const isForm = body instanceof FormData

  const reqHeaders = { Accept: 'application/json', ...headers }
  if (body && !isForm && !('Content-Type' in reqHeaders)) {
    reqHeaders['Content-Type'] = 'application/json'
  }

  if (auth) {
    const token = tokenStore.getAccess()
    if (token) reqHeaders.Authorization = `Bearer ${token}`
  }

  const doFetch = () =>
    fetch(url, {
      method,
      headers: reqHeaders,
      body: body == null ? undefined : isForm ? body : JSON.stringify(body),
    })

  let res = await doFetch()

  // Auto-refresh on 401 (skip the refresh endpoint itself to avoid recursion)
  if (res.status === 401 && auth && !path.includes('/auth/refresh') && !path.includes('/auth/login')) {
    try {
      const newToken = await refreshAccessToken()
      reqHeaders.Authorization = `Bearer ${newToken}`
      res = await doFetch()
    } catch (e) {
      // refresh failed — fall through to error handling below
    }
  }

  if (raw) return res

  if (!res.ok) {
    const data = await parseBody(res)
    const code = (data && (data.code || data.detail)) || res.statusText
    const message =
      (data && (data.message || data.detail)) ||
      (typeof data === 'string' ? data : null) ||
      `Request failed (${res.status})`
    throw new ApiError(res.status, code, message, data)
  }

  if (res.status === 204) return null
  return parseBody(res)
}

export const api = {
  get: (path, opts) => request('GET', path, opts),
  post: (path, body, opts) => request('POST', path, { ...opts, body }),
  patch: (path, body, opts) => request('PATCH', path, { ...opts, body }),
  put: (path, body, opts) => request('PUT', path, { ...opts, body }),
  del: (path, opts) => request('DELETE', path, opts),
}

export const BASE = BASE_URL

/**
 * Returns the origin (scheme + host + port) of the backend, derived from
 * VITE_API_BASE_URL. Used to resolve media URLs returned by Django, which
 * are relative paths like "/media/avatars/xyz.jpg".
 *
 *  - VITE_API_BASE_URL = "http://localhost:8000/api/v1"  →  "http://localhost:8000"
 *  - VITE_API_BASE_URL = "/api/v1" (Vite proxy)          →  window.location.origin
 */
export function backendOrigin() {
  if (BASE_URL.startsWith('http')) {
    try { return new URL(BASE_URL).origin } catch { /* fall through */ }
  }
  return typeof window !== 'undefined' ? window.location.origin : ''
}

/**
 * Resolve a possibly-relative URL (e.g. an avatar or media URL returned
 * by Django) against the backend origin so <img src> works in the browser.
 */
export function resolveMediaUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url) || url.startsWith('data:')) return url
  const origin = backendOrigin()
  return url.startsWith('/') ? `${origin}${url}` : `${origin}/${url}`
}

export function logoutLocally(reason = 'user_logout') {
  tokenStore.clear()
  emitAuthChange({ type: 'logout', reason })
}
