// Service-worker registration + lightweight update bus.
//
// Importing this module has a side effect: on production builds it registers
// /sw.js once the window has loaded, and wires a small EventTarget so React
// components can react to lifecycle events without taking a hard dependency
// on the SW APIs.
//
// Events on `pwaBus`:
//   'update-available'  — a new worker finished installing and is waiting.
//   'controllerchange'  — the new worker has taken over (page should reload).

// Single bus everyone subscribes to. Plain EventTarget keeps the bundle tiny.
export const pwaBus = new EventTarget()

let waitingWorker = null

/** Tell the waiting worker to activate, then reload once it does. */
export function applyUpdate() {
  if (!waitingWorker) return
  // One-shot reload trigger: when the new SW takes over we refresh the page
  // so it picks up the new bundle in one clean shot. Guarded by a flag so
  // we don't double-reload if multiple updates queue up in dev.
  if (!applyUpdate._wired) {
    applyUpdate._wired = true
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      pwaBus.dispatchEvent(new Event('controllerchange'))
      window.location.reload()
    })
  }
  waitingWorker.postMessage({ type: 'SKIP_WAITING' })
}

export function registerServiceWorker() {
  if (typeof window === 'undefined') return
  if (!('serviceWorker' in navigator)) return
  // Dev server: Vite serves files from /src and doesn't ship /sw.js, so
  // registering would just spam errors. import.meta.env.PROD is true in
  // `vite build` output, false during `vite dev`.
  if (!import.meta.env.PROD) return

  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js', { scope: '/' })

      // Surface an update event the first time a *new* worker is waiting.
      // We treat `reg.waiting` (already-installed-on-load) and the
      // `updatefound` flow (installed-while-running) the same way.
      const announce = (worker) => {
        waitingWorker = worker
        pwaBus.dispatchEvent(new Event('update-available'))
      }

      if (reg.waiting && navigator.serviceWorker.controller) announce(reg.waiting)

      reg.addEventListener('updatefound', () => {
        const installing = reg.installing
        if (!installing) return
        installing.addEventListener('statechange', () => {
          if (installing.state === 'installed' && navigator.serviceWorker.controller) {
            announce(installing)
          }
        })
      })

      // Probe for updates once an hour while the tab stays open — cheap and
      // catches the long-lived-tab case where the user never reloads.
      setInterval(() => reg.update().catch(() => {}), 60 * 60 * 1000)
    } catch (e) {
      // Registration is best-effort. Failing it shouldn't break the app.
      console.warn('[pwa] SW registration failed', e)
    }
  })
}
