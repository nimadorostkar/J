// Houston / TokenVault service worker.
//
// Strategy summary
// ────────────────
// • Navigation requests (HTML)  → network-first, fall back to cached
//                                  /offline.html when both network and any
//                                  cached copy are unavailable.
// • Same-origin static assets  → stale-while-revalidate (fast loads, fresh
//                                  in the background).
// • API + WebSocket calls       → always go to the network. We never cache
//                                  /api or /ws; that would lie to the user
//                                  about balances, sessions, etc.
// • Cross-origin requests       → passthrough (let the browser handle).
//
// Updates
// ───────
// On `message: { type: 'SKIP_WAITING' }` the new worker activates immediately
// — used by the in-app "Update available" prompt. On install we precache the
// app shell; on activate we delete old versions of our caches.
//
// Bump CACHE_VERSION whenever cache-keying behaviour changes; this triggers
// an upgrade for every existing client on the next page load.

const CACHE_VERSION = 'v1'
const PRECACHE  = `houston-precache-${CACHE_VERSION}`
const RUNTIME   = `houston-runtime-${CACHE_VERSION}`
const OFFLINE_URL = '/offline.html'

// App-shell URLs that should always be available offline.
const PRECACHE_URLS = [
  '/',
  '/offline.html',
  '/manifest.webmanifest',
  '/favicon.png',
  '/icon-192.png',
  '/icon-512.png',
  '/apple-touch-icon.png',
]

/* ── install: precache the app shell ──────────────────────────────────── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(PRECACHE)
      // `addAll` is atomic — if any one fails, none are cached. We swallow
      // individual errors with allSettled because a missing icon shouldn't
      // brick the entire SW install.
      await Promise.allSettled(
        PRECACHE_URLS.map((u) => cache.add(new Request(u, { cache: 'reload' }))),
      )
    })(),
  )
})

/* ── activate: clean up old cache buckets ────────────────────────────── */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keep = new Set([PRECACHE, RUNTIME])
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)))
      // Take over open pages immediately.
      await self.clients.claim()
    })(),
  )
})

/* ── update prompt: in-app code posts SKIP_WAITING to swap to the new SW ─ */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

/* ── fetch ───────────────────────────────────────────────────────────── */
self.addEventListener('fetch', (event) => {
  const req = event.request
  // We only handle GETs. POST/PUT etc. would also be wrong to cache.
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return  // cross-origin → passthrough

  // Never touch the API or WebSocket. Always go to the network. This is the
  // single most important rule — caching /api would show stale balances.
  if (url.pathname.startsWith('/api') || url.pathname.startsWith('/ws')) return

  // HTML navigations: network-first with offline fallback.
  const isHtml =
    req.mode === 'navigate' ||
    (req.headers.get('accept') || '').includes('text/html')
  if (isHtml) {
    event.respondWith(networkFirstHtml(req))
    return
  }

  // Everything else under our origin: stale-while-revalidate.
  event.respondWith(staleWhileRevalidate(req))
})

/* ── strategies ───────────────────────────────────────────────────────── */

async function networkFirstHtml(req) {
  const cache = await caches.open(RUNTIME)
  try {
    const res = await fetch(req)
    // Only cache successful, non-opaque responses.
    if (res && res.ok) cache.put(req, res.clone())
    return res
  } catch {
    // Network failed → cached copy of this URL, then cached "/", then offline page.
    const cached = (await cache.match(req)) || (await caches.match('/'))
    if (cached) return cached
    const offline = await caches.match(OFFLINE_URL)
    return offline || new Response('Offline', { status: 503, statusText: 'Offline' })
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(RUNTIME)
  const cached = await cache.match(req)
  const network = fetch(req)
    .then((res) => {
      if (res && res.ok) cache.put(req, res.clone())
      return res
    })
    .catch(() => undefined)
  // Return cached version immediately if we have one; otherwise wait for
  // the network. If the network ALSO fails (offline cold-start), let the
  // browser surface its own error — there isn't a sensible fallback for an
  // arbitrary asset.
  return cached || (await network) || new Response('', { status: 504 })
}
