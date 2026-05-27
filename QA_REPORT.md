# TokenVault / Houston — QA Report

**Date:** 2026-05-27
**Tester:** Claude (acting as QA + end-user)
**Build under test:** `tokenvault/` (React/Vite SPA) + `backend/` (Django + DRF + Celery)
**Frontend:** http://localhost:5173 · **Backend admin:** http://localhost:8000/admin/

---

## 0. Scope & Method — read this first

I was asked to "test the entire application like a real customer." I attempted to do that against the running services at `localhost:5173` and `localhost:8000`, but:

1. **No Chrome browser is connected** to the Claude in Chrome extension (the list-connected-browsers call returned an empty list).
2. The sandbox **cannot reach your localhost** — those ports are only bound on your machine.
3. **Computer use is disabled** (Settings → Desktop app → Computer use).

So real click-through testing was impossible from where I'm running. I pivoted to a **rigorous static QA pass over the actual source** — reading every page, modal, context, API wrapper, and the relevant backend views/settings, looking for the same defects a runtime tester would surface: broken flows, missing validation, security holes, dead/inconsistent UX, i18n bugs, and accessibility gaps.

If you'd like a true runtime pass (clicking through, screenshots, console/network capture), enable Computer use OR install the Claude in Chrome extension and reopen this thread — I can re-run the whole suite live.

---

## 1. Bug list

Severity scale: **P0** blocker · **P1** major · **P2** moderate · **P3** minor/cosmetic.

### P0 — Blockers

#### BUG-001 · Deposit QR shows the wrong (global) address for users with a per-user address
- **File:** `backend/wallet/views.py` lines 82–121
- **Steps to reproduce:** Ops assigns a per-user `DepositAddress` to user A. User A opens Wallet → Deposit.
- **Expected:** Text address and QR both encode the user's personal `DepositAddress.address`.
- **Actual:** Text shows the per-user address (line 96–99), but `DepositAddressQRView` (line 117) **always** encodes `settings.USDT_TRC20_WALLET` / `USDT_ERC20_WALLET`. Users will scan the QR and pay to the wrong wallet — funds will not be credited and may be unrecoverable.
- **Severity:** P0 — financial loss.

#### BUG-002 · Deposit QR `<img>` will never load (auth header not sent on image requests)
- **File:** `tokenvault/src/components/DepositModal.jsx` line 132; `backend/wallet/views.py` line 113
- **Steps:** Open Wallet → Deposit on a logged-in account.
- **Expected:** QR image renders.
- **Actual:** `<img src={walletApi.depositAddressQrUrl(network)}>` issues a plain GET with no `Authorization` header. The endpoint is `permission_classes = [IsAuthenticated]`, so the response is 401 and the `<img>` fails. Either make the endpoint signed-URL or render the QR client-side from the address.
- **Severity:** P0 — primary deposit UI broken.

#### BUG-003 · Password reset does not invalidate JWT sessions
- **File:** `backend/users/views.py` lines 188–213 (`ResetPasswordView`)
- **Steps:** Attacker compromises a refresh token. Victim resets their password via "Forgot password."
- **Expected:** All access + refresh tokens issued before the reset are invalidated.
- **Actual:** Only `password` is rewritten (line 209); outstanding refresh tokens remain valid until they expire (default 7 days). The attacker keeps full access after the reset.
- **Severity:** P0 — security.

### P1 — Major

#### BUG-004 · Network L2 graph plots fake parent–child edges
- **File:** `tokenvault/src/pages/Network.jsx` line 110
- **Detail:** `const parent = l1Positions[i % l1Positions.length]` assigns each level-2 node to a level-1 node **by array index modulo**, not by the real `parent` field returned by the backend. The connecting lines in the galaxy chart are therefore misleading.
- **Expected:** Lines connect each L2 referral to the actual L1 user who invited them.
- **Severity:** P1 — visual lies in a feature whose entire purpose is showing the referral graph.

#### BUG-005 · Transaction descriptions are hardcoded English regardless of language
- **File:** `tokenvault/src/context/WalletContext.jsx` lines 11–19
- **Detail:** `TYPE_LABELS = { deposit: 'USDT Deposit', withdraw: 'Withdrawal', … }` is plain English. The whole rest of the app translates via `useT()`. Persian, etc. users see English in their tx list.
- **Severity:** P1 — i18n regression on the most-viewed list in the app.

#### BUG-006 · Reset-password page silently swallows "missing token" error
- **File:** `tokenvault/src/pages/ResetPassword.jsx` lines 22–29
- **Detail:** If `token` query-param is missing, `errs.token` is set but no `Field`/banner ever displays `errors.token`. The Submit button does nothing visible.
- **Repro:** Visit `/reset-password` with no `?token=…`, fill the new-password fields, click Submit.
- **Expected:** Clear "missing or invalid reset link" banner with a CTA to request a new link.
- **Actual:** Click does nothing, no toast, no error.
- **Severity:** P1.

#### BUG-007 · Withdraw address validation is "length ≥ 10" with no chain check (client side)
- **File:** `tokenvault/src/components/WithdrawModal.jsx` line 48
- **Detail:** Pasting `1234567890` passes client validation. Server validates (good), but no immediate feedback. A TRC20 address pasted while ERC20 tab is selected isn't flagged client-side. High risk of sending to the wrong network.
- **Expected:** Inline error: "Address doesn't match selected network."
- **Severity:** P1.

#### BUG-008 · Live-chat "Support" button just shows a session token in a toast
- **File:** `tokenvault/src/pages/Profile.jsx` lines 360–365
- **Detail:** Clicking "Live chat" calls `supportApi.chatSession()` and displays the raw `sessionToken` to the user. There is no chat UI. Feature is shipped half-built.
- **Severity:** P1 (UX) / P3 (security — token in a toast).

#### BUG-009 · Password-length rules differ between Login and Register
- **Files:** `Login.jsx` line 31 (`< 6`), `Register.jsx` line 47 (`< 8`), `Profile.jsx` line 138 (`< 8`).
- **Detail:** Existing users who set a 6–7 char password cannot log in (validation blocks before request), but can never raise the issue because forgot-password also enforces 8. They are locked out client-side.
- **Severity:** P1.

#### BUG-010 · Profile form state captures `user` once at mount; never refreshes
- **File:** `tokenvault/src/pages/Profile.jsx` lines 40–48
- **Detail:** `useState({ firstName: user?.firstName || '', … })` runs once. If `user` arrives a tick later (cold-load with auto-refresh), the form is permanently empty for that session. Hard refresh required.
- **Severity:** P1.

#### BUG-011 · `SECRET_KEY` falls back to a dev string in prod if env var is missing
- **File:** `backend/core/settings/base.py` line 12
- **Detail:** `SECRET_KEY = config("SECRET_KEY", default="insecure-dev-secret-change-me")`. Used as `SIGNING_KEY` for JWT (line 185). A misconfigured prod deploy silently issues tokens an attacker can forge.
- **Fix:** In `prod.py`, override with `SECRET_KEY = config("SECRET_KEY")` and let the app crash if unset.
- **Severity:** P1 — security.

### P2 — Moderate

#### BUG-012 · Notification polling runs in hidden tabs / battery drain
- **File:** `tokenvault/src/pages/Wallet.jsx` line 56
- **Detail:** `setInterval(…, 30_000)` keeps polling `notifications/unread-count` even when the tab is backgrounded or the user is on another page. Should pause on `document.visibilityState === 'hidden'`.
- **Severity:** P2 (battery + bandwidth).

#### BUG-013 · `wallet.transactions.length` not optional-chained
- **File:** `tokenvault/src/pages/Wallet.jsx` line 298
- **Detail:** If `WalletContext` fails to load (network error during first paint), `wallet.transactions` may not be the seeded array — accessing `.length` could throw. The skeleton is gated on `loading` only, not on shape.
- **Severity:** P2.

#### BUG-014 · `Network.jsx` `useEffect` deps array missing `t`
- **File:** `tokenvault/src/pages/Network.jsx` line 87
- **Detail:** Status labels are computed once at fetch time using whatever `t` was at first render. Change language mid-session → status pills (Verified, Qualified, etc.) stay in the old language until a hard reload.
- **Severity:** P2 (i18n).

#### BUG-015 · `BottomSheet` modals lack `role="dialog"`, `aria-modal`, focus trap
- **File:** `tokenvault/src/components/BottomSheet.jsx`
- **Detail:** Screen readers don't announce as a dialog. Tab key escapes back to underlying page. Focus is not moved into the sheet nor restored on close. Affects every Deposit/Withdraw flow.
- **Severity:** P2 (accessibility).

#### BUG-016 · CORS contradiction in dev: `ALLOW_ALL_ORIGINS=True` + `ALLOW_CREDENTIALS=True`
- **File:** `backend/core/settings/dev.py` lines 11–12
- **Detail:** Browsers reject credentialed requests when the server responds `Access-Control-Allow-Origin: *`. Django-cors-headers handles this by echoing the origin, but it's a footgun: if anyone ships `dev.py` to prod (or copies the pattern), real cross-origin auth requests will silently break.
- **Severity:** P2.

#### BUG-017 · Reset-token TTL hardcoded to 1 hour; no countdown in UI
- **File:** `backend/users/views.py` line 202 (`60 * 60`)
- **Detail:** No env override and the frontend never tells the user "this link expires at 14:53."
- **Severity:** P2.

#### BUG-018 · Transaction dates display in UTC, no locale formatting
- **File:** `tokenvault/src/context/WalletContext.jsx` line 36
- **Detail:** `d.toISOString().slice(0, 16).replace('T', ' ')` — every user sees UTC, no AM/PM, no locale. A user in Tehran sees `2026-05-27 09:12` for a deposit they made at 12:42 local.
- **Severity:** P2.

### P3 — Minor / cosmetic

- **BUG-019:** `Wallet.jsx` line 309 shadows `t` (translator) with a per-transaction `t` inside `.map((t) =>` — works today, will bite the next dev.
- **BUG-020:** `ForgotPassword.jsx` field has no inline error display (only toast); inconsistent with the rest of the app (`Field` accepts an `error` prop everywhere else).
- **BUG-021:** `Profile.jsx` line 199 — disabled email field still has `onChange` wired (dead code).
- **BUG-022:** `Profile.jsx` line 374 — support email `support@tokenvault.io` hardcoded; should be env-driven.
- **BUG-023:** `Register.jsx` line 50 — invite-code regex accepts mixed case; `.toUpperCase()` runs only on submit, so the user sees lowercase letters they typed silently mutated.
- **BUG-024:** `DepositModal.jsx` line 67 — `txHash` accepted with no format check; the placeholder "0x… or T…" suggests two formats but neither is validated client-side.
- **BUG-025:** `Trade.jsx` line 98 — 30 s poll runs forever while bot is active, even when tab is hidden; same problem as BUG-012.
- **BUG-026:** `Wallet.jsx` line 64 — 1 Hz `setInterval` to nudge the progress bar; CSS transition could do this with one keyframe and zero JS.
- **BUG-027:** `ActiveBotCard` (Trade) `useEffect` calls `onComplete` immediately if `ms <= 0`, then again via `setTimeout`. Duplicate refresh on every render once expired.
- **BUG-028:** `WithdrawModal.jsx` line 27 — `usdtEquiv = tokens * conversion` shown even when `tokens > balance` (invalid state). No visual indication you've gone over.
- **BUG-029:** `Profile.jsx` `StatusChip` uses `<span>○</span>` as the inactive icon (literal Unicode bullet). Renders different sizes across fonts and OSes.

---

## 2. Things I could NOT verify without runtime access

These need a live click-through; flagging them as "open" rather than passing them:

- Visual responsiveness on mobile viewports (the SPA is constrained to `max-w-[480px]`, so it is mobile-shaped, but I cannot confirm safe-area handling on a real iPhone or PWA install).
- Loading-state shimmer for `WalletSkeleton` actually matches final layout (no CLS).
- Toast queue behavior under rapid-fire errors.
- 401-driven auto-refresh actually works against a real refresh response (cannot exercise the `/auth/refresh/` round-trip).
- Real network errors / offline behavior.
- Payment-provider sandbox flows (not present in this codebase — there is no Stripe/PayPal integration; on-chain only).
- Console errors and network 4xx/5xx from a real session.
- Django admin permissions, model search/filter behavior, fixture data.

If you re-enable Computer use I will run those next.

---

## 3. Overall quality assessment

**Strengths**
- Clean React + Vite layout, sensible page split, route guards (`Protected`/`Public`).
- Solid auth scaffolding: refresh-token rotation, login throttle, register throttle, password-reset throttle, audit log calls.
- Backend wallet code uses `select_for_update` + `db_tx.atomic()` + an idempotency key on deposit and withdraw — correct concurrency story.
- Withdraw eligibility gated through a service (`assert_can_withdraw`) instead of view-level checks. Good separation.
- i18n infrastructure in place (`useT`, language picker, per-locale dictionaries).
- JWT TTLs are short (15 min access, 7 day refresh) — good defaults.

**Weaknesses**
- The deposit QR pipeline is broken end-to-end (BUG-001 + BUG-002). A user funding the app for the first time will likely fail.
- Half-built support feature (BUG-008) shouldn't be in a production cut.
- Translation coverage is incomplete in the transaction list — a key surface (BUG-005).
- Inconsistent password rules between login and register (BUG-009) will cause real lock-outs.
- Accessibility is weak across all modals (BUG-015) — fails WCAG 2.1 AA dialog requirements.
- Several `useEffect` polling loops never pause; on a phone with the app idling in the background, this will drain battery and quota.

---

## 4. Performance suggestions

1. **Pause all polling on `visibilitychange`** — Wallet notifications (30 s), Trade refresh (30 s), Wallet/Trade `setInterval(…, 1000)` countdowns. Wire one `useVisibility()` hook and gate them.
2. **Replace 1 Hz progress-bar nudge with a single CSS animation** — set `transition: width Xs linear` and update `width` once. Removes React reconciliation cost.
3. **Render the deposit QR client-side** (e.g., `qrcode-svg` or `qr-code` web component) — kills a round-trip per modal open and fixes BUG-002.
4. **Cache `/reference/countries` and `/support/faqs`** — they're loaded on every Profile visit. Stale-while-revalidate with `localStorage` is enough.
5. **Avoid recreating `Promise.allSettled` chains on every render** — `Network.jsx`'s effect refetches network, code, and stats together; consider splitting so a fast endpoint isn't blocked by a slow one.
6. **Memoize `l1Positions` / `l2Positions` properly** — currently keyed on `CENTER` which never changes; the `useMemo` is doing nothing useful and re-runs anyway on every parent render.
7. **Throttle SVG `<animate>` on the network galaxy** — when there are 50+ L1 nodes, the always-on `animate-spin-slow` group will pin a CPU core on low-end devices.

---

## 5. Security concerns

| # | Concern | Where | Risk |
|---|---|---|---|
| S1 | `SECRET_KEY` dev fallback in prod | base.py:12 | JWT forgery |
| S2 | Password reset doesn't revoke sessions | users/views.py:188 | Persistent attacker access |
| S3 | Deposit QR doesn't require auth (it does, but is then loaded as `<img>` — see BUG-002); if you make it public to fix the load, addresses leak | wallet/views.py:112 | Address enumeration |
| S4 | Per-user vs global wallet mismatch in QR | wallet/views.py:117 | Misdirected funds |
| S5 | Live-chat session token displayed in a toast | Profile.jsx:363 | Shoulder-surfing / accidental screenshot |
| S6 | `CORS_ALLOW_ALL_ORIGINS = True` in dev with credentials | dev.py:11 | Footgun, not directly exploitable |
| S7 | Throttle rates raised to 10k/min in dev | dev.py:15 | If dev settings ship, no brute-force protection |
| S8 | Forgot-password timing oracle | users/views.py:170 | Possible user enumeration via response time |
| S9 | No CSRF on the API (relies on JWT in `Authorization`) — fine, but combined with `CORS_ALLOW_ALL_ORIGINS` in dev it means any page could call the API if a user's token leaks. | settings/dev.py | Defense in depth |
| S10 | No `Content-Security-Policy` or `Permissions-Policy` headers configured | prod.py | Standard hardening missing |

---

## 6. Production readiness score

**Score: 5.5 / 10**

Reasoning: The architecture is in good shape and the auth/financial code paths use the right primitives (atomic + select_for_update + idempotency). But two **P0** issues directly affect the very first money-in flow a new user will try (deposit QR points to the wrong wallet, and the QR image can't even render), and a third **P0** undermines the entire account-recovery story. Until those three are fixed, this is not ready to take real users' funds. Once they are, with the P1 fixes layered in, this codebase can move to a 7.5–8 quickly.

**Ship-blocking items before going live:**
1. BUG-001 (per-user QR address)
2. BUG-002 (QR image auth)
3. BUG-003 (revoke tokens on password reset)
4. BUG-011 (prod `SECRET_KEY` fallback)
5. BUG-009 (login/register password rule mismatch)
6. BUG-005 (translate transaction labels)
7. BUG-008 (remove or finish live chat)

Everything else can ship as a backlog and be patched in the first iteration.
