# TokenVault — Balance Behavior Reference

A comprehensive walk-through of every code path in the TokenVault backend that
can credit, debit, or otherwise affect a user's wallet balance, plus the
business rules, idempotency guarantees, and configuration knobs around each
one.

The intent of this document is to be the **single source of truth** for "what
makes a balance go up or down" — useful for QA testing, accounting reconciliation,
and onboarding new contributors.

---

## 1. The currency model

| Concept | What it is | Where stored | Decimals |
|---|---|---|---|
| **H Coin** | The internal platform token. All rewards, fees, and bonuses are denominated in H. | `Wallet.h_coin_balance` (DB) | 8 |
| **USDT** | External stablecoin used to fund deposits and pay out withdrawals. Not actually held in the wallet — the wallet keeps a USDT *snapshot* equal to `h_coin_balance × conversion_rate`. | `Wallet.usdt_balance` | 8 |
| **Conversion rate** | 1 H Coin = `USDT_PER_HCOIN` USDT (default **10**). | `settings.USDT_PER_HCOIN` | — |

In all places where the user sees "USDT equivalent" of an H Coin amount, that's
just `h_coin_balance × USDT_PER_HCOIN` — there's no exchange involved. The two
numbers always move in lock-step.

### Wallet model — read-only flags

| Field | Meaning | Set by |
|---|---|---|
| `has_completed_deposit` | True after the user's first successfully confirmed deposit. | `verify_deposit` / admin force-complete |
| `has_referral` | Cached "user has ≥ 1 *qualified* L1 referral" — referral with a completed deposit. | Self-healed by the activation guard |
| `reward_active` | True while a per-user reward cycle is in flight. | Cycle activate/claim |
| `reward_end_time` | When the active cycle becomes claimable. | Cycle activate |

---

## 2. Deposits — money in

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/wallet/networks/` | List supported networks + fees/minimums |
| `GET`  | `/api/v1/wallet/deposit-address/?network=TRC20` | Returns the deposit address + QR URL |
| `GET`  | `/api/v1/wallet/deposit-address/qr/?network=…` | Renders the QR as a PNG |
| `POST` | `/api/v1/wallet/deposit/` | Initialises a new deposit tx |
| `GET`  | `/api/v1/wallet/deposit/<tx_id>/` | Polls the status of a single deposit |

### Networks

| Network | Symbol | Notes |
|---|---|---|
| TRC20 | Tron | Lower fees, faster confirmations |
| ERC20 | Ethereum | More expensive but widely supported |

Both networks share the same per-platform minimum of `MIN_DEPOSIT_USDT`
(default **10 USDT**).

### Flow

1. The frontend calls `POST /wallet/deposit/` with `{network, amountUsdt, txHash?}`.
   A header `Idempotency-Key: <uuid>` is recommended; if absent, the server
   generates one.
2. The server creates a `Transaction(type=deposit, status=pending)` row and
   queues `verify_deposit.delay(tx_id)` on Celery.
3. `verify_deposit` polls the blockchain (`_check_chain_confirmation`,
   currently a stub returning True if any tx_hash is present — replace with
   the real Tron/Etherscan client for production).
4. Once confirmed, inside one atomic block:
   * `wallet.usdt_balance += tx.amount_usdt`
   * if it's the user's first ever completed deposit, `wallet.has_completed_deposit = True`
   * `tx.status = completed`
   * Audit row: `deposit_complete` with `first_deposit=True/False`
5. **After the commit**, if this was the user's first deposit, the system
   calls `referrals.services.on_deposit_completed(user)` — this is what makes
   the user "qualify" as a referral for their L1 inviter and potentially
   trigger a milestone reward (see §6.2).
6. A WebSocket event `transaction_update` and `balance_update` is pushed to
   the user, and a `Notification` row is created (subject "Deposit confirmed").

### Balance impact

| Source field | Effect | Tx Type |
|---|---|---|
| `wallet.usdt_balance` | `+= amount_usdt` | `deposit` |
| `wallet.h_coin_balance` | unchanged here — H Coins are minted only by reward/bot/milestone payouts, not by deposits. | — |

⚠️ Important: in the current model, depositing USDT **does not directly mint
H Coins**. The deposit's H Coin equivalent (`amount_usdt / USDT_PER_HCOIN`)
is stored on the transaction row but not added to the wallet's
`h_coin_balance` — that happens via reward cycles and bots. The deposit's
real purpose is (a) to mark the user as having ever paid in, and (b) to
trigger downstream referral qualification.

### Throttling / safety

* **Idempotency-Key**: per-user unique constraint on `(user, idempotency_key)`
  on the Transaction table. A duplicate POST returns the same Transaction row
  instead of creating a second one.
* **Pending expiry**: `expire_stale_deposits` Celery task runs periodically
  and flips any `deposit, status=pending` older than 24h to `failed`.

### Forced completion (admin)

The Django admin has a `force_complete_deposit` action on the Transaction
list. It does the same wallet/audit work as `verify_deposit` and also calls
`on_deposit_completed(user)` for each first-deposit, so a manually-approved
deposit qualifies the user just like a chain-confirmed one.

---

## 3. Withdrawals — money out

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/wallet/withdraw/eligibility/` | Returns `{eligible, reason}` |
| `POST` | `/api/v1/wallet/withdraw/` | Initialises a withdrawal |
| `GET`  | `/api/v1/wallet/withdraw/<tx_id>/` | Polls a withdrawal's status |

### Throttle

3 withdrawals per minute per user (`WithdrawThrottle`) — DRF rate-limit.

### Flow

1. `assert_can_withdraw(user)` runs first. If it raises `WithdrawalLocked`,
   the global exception handler returns `403`. Reasons can include "user
   recently changed password", "KYC pending", etc.
2. The destination address is validated (TRC20 / ERC20 specific regex via
   `validate_address`).
3. Inside an atomic block with `SELECT FOR UPDATE` on the wallet:
   * Confirms `h_coin_balance >= tokens`.
   * `wallet.h_coin_balance -= tokens`.
   * Creates `Transaction(type=withdraw, status=pending, amount_usdt = tokens*USDT_PER_HCOIN − fee, amount_hcoin = tokens, wallet_address = address)`.
   * Encrypted-at-rest: `wallet_address` is `EncryptedCharField`.
   * Idempotency-Key header is honored (same as deposits).
4. If `WITHDRAWAL_AUTO_APPROVE=True`, `process_withdrawal.delay(tx_id)` is
   queued immediately. Otherwise it waits for an admin to approve via the
   Django admin's `approve_withdrawals` action.
5. `process_withdrawal` simulates a chain transfer (current code uses a
   `simulated-{txid}` hash placeholder — replace with a real hot-wallet
   signer). On success, `tx.tx_hash` is recorded and status flips to
   `completed`. On failure, `tx.status = failed` and the H Coins are
   **refunded** back to the wallet atomically.

### Fees

* `WITHDRAWAL_FEE_USDT` (default **1 USDT**) is deducted from the user-facing
  `amount_usdt` field — the chain transfer is for `tokens × rate − fee`.
* H Coin amount (`tokens`) is debited at full requested value — the fee is
  paid out of the USDT side.

### Balance impact

| Step | Effect | Tx Type |
|---|---|---|
| Init  | `h_coin_balance -= tokens` | `withdraw` (pending) |
| Success | (no further wallet write — chain transfer only) | `withdraw` (completed) |
| Failure | `h_coin_balance += tokens` (refund) | `withdraw` (failed) |

---

## 4. Reward Cycle — the 15-day bonus

### Definition

Once a user is eligible, they activate a per-user "reward cycle". After
`REWARD_DURATION_DAYS` (default **15 days**), the cycle becomes claimable.
On claim, the user is paid `REWARD_PERCENT %` (default **20 %**) of the
H Coin balance they had at activation time.

The amount is **snapshotted at activation** so there's no economic incentive
to top up the wallet right before claiming.

### Activation eligibility

Both must be true:

1. `h_coin_balance > 0`
2. The user has **≥ 1 qualified L1 referral** (an invited user who has made
   at least one completed deposit — see §6.1).

If either is missing, `POST /api/v1/reward/cycle/activate/` returns `400`
with a `reasons[]` array — the SPA shows the failed conditions inline
and disables the button.

The `GET /api/v1/reward/cycle/` no-cycle response includes
`{canActivate, ineligibilityReasons}` so the UI can disable the button
*before* the user clicks it.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/reward/cycle/` | Active cycle, or a no-cycle preview with the expected payout |
| `POST` | `/api/v1/reward/cycle/activate/` | Start a cycle |
| `POST` | `/api/v1/reward/cycle/claim/` | Finalize a ready cycle (Idempotency-Key honored) |
| `GET`  | `/api/v1/reward/global-cycle/` | Platform-wide "season" countdown (separate from per-user) |

### Activation

```python
amount = max(balance * REWARD_PERCENT / 100, REWARD_MIN_HCOIN)
RewardCycle.objects.create(
    user=user,
    reward_amount_hcoin=amount,         # snapshot
    ends_at=now + timedelta(days=REWARD_DURATION_DAYS),
    status="active",
)
```

There's no fee for activating — the activation just locks the user out of
starting another cycle until they claim. `REWARD_MIN_HCOIN` (default **1**)
is a floor so even users with tiny balances get something on their first
cycle.

### Claim

After `ends_at` has passed:

```python
wallet.h_coin_balance += cycle.reward_amount_hcoin
cycle.status = "claimed"
Transaction.objects.create(type="reward", amount_hcoin=amount, status="completed")

# Side effect: pay referral commissions on this profit
distribute_commission(user, amount)
```

### Distribution to inviters

`distribute_commission(user, profit)` runs inside the same atomic block and
pays the L1 (and L2, if any) inviters:

* L1 inviter: `profit × REFERRAL_L1_COMMISSION_PCT / 100` (default **5 %**)
* L2 inviter (grandparent): `profit × REFERRAL_L2_COMMISSION_PCT / 100` (default **3 %**)

Each commission becomes its own `Transaction(type=commission)` row with
`commission_from_user`, `commission_level`, `commission_rate` populated, so
the audit trail records who earned what from whom.

### Balance impact

| Step | Acting user | Effect | Tx Type |
|---|---|---|---|
| Activate | self | none — just locks the cycle | — |
| Claim | self | `+= reward_amount_hcoin` (the snapshot) | `reward` |
| Claim | L1 inviter | `+= profit × 5 %` | `commission` (level 1) |
| Claim | L2 inviter | `+= profit × 3 %` | `commission` (level 2) |

### Global cycle

Separate from per-user cycles, there's a single "season" countdown the
homepage shows. Configured by `GLOBAL_CYCLE_END_DATE` (default
**2026-10-01**) — `_ensure_global_cycle()` rewrites the existing cycle
in-place each time the endpoint is hit so the target stays accurate.

---

## 5. Referral System

### 5.1 Referral graph

Two levels:

* **Level 1 (L1)** — direct: someone who registered using your invite code.
* **Level 2 (L2)** — grand-child: someone who registered using your L1's
  invite code.

A user's invite code is auto-assigned at registration (`User.referral_code`,
8 alphanumeric characters). The referral graph is stored in `referrals.Referral`
with a unique constraint on `(inviter, invited_user, level)` so the same
person can't be counted twice at the same level.

### 5.2 The "qualified" rule (anti-fake-account)

Only **L1 referrals whose invited user has at least one completed deposit**
count toward milestone rewards and the reward-cycle activation guard.
Signups alone are tracked and visible but earn no economic reward to the
inviter.

This is enforced by the `Referral.objects.qualified_for(user)` queryset,
which joins through to `Transaction` looking for any `deposit, status=completed`
for the invited user.

The four statuses surfaced to the API and the UI:

| Status | Condition |
|---|---|
| `registered` | Row exists in `referrals.Referral` |
| `verified` | + `users.User.is_email_verified = True` |
| `first_deposit_completed` | + at least one completed deposit |
| `qualified` | + `level == 1` (only direct invites count) |

The Network page shows status badges per referral (color-coded ring +
status pipeline in the node popup).

### 5.3 Commissions on reward claims (§4 above)

* **L1: 5 %** of the invited user's claimed reward amount.
* **L2: 3 %** of the same amount.

These pay regardless of qualification — they're triggered by the invited
user claiming a reward, not by their referral row's status. (Note that to
*claim* a reward the invited user themselves must have a qualified L1, so
in practice they're already economically active.)

`Referral.total_commission_earned_hcoin` accumulates these payouts so the
inviter's stats endpoint can show lifetime commission earned.

### 5.4 Milestone rewards

Every Nth qualified L1 referral pays the inviter a flat coin bonus.

| Knob | Default |
|---|---|
| `REFERRAL_MILESTONE_SIZE` | 5 |
| `REFERRAL_MILESTONE_REWARD_HCOIN` | 1 |

So at qualified counts of 5, 10, 15, … the inviter is paid 1 H Coin.

#### Trigger points

1. **Registration** — the `pay_referral_milestones(inviter)` call runs after
   each new L1 referral is created. Because the new user hasn't deposited
   yet, this call typically pays nothing — but it's run defensively to
   pick up any backfilled state.
2. **First deposit completion** — `on_deposit_completed(user)` finds the
   L1 inviter and runs `pay_referral_milestones(inviter)`. This is the
   real qualifying event.
3. **Backfill** — `python manage.py backfill_referral_milestones` walks
   every user with referrals and pays any unpaid milestones. Safe to re-run.

#### Idempotency

The `ReferralMilestoneReward` table has `UniqueConstraint(user, milestone)`.
Even under racing concurrent registrations, the database makes it
impossible for the same user to be paid twice for milestone 5 (or any other).
`pay_referral_milestones` catches the `IntegrityError` and skips silently.

#### Balance impact per milestone reached

| Step | Effect | Tx Type |
|---|---|---|
| Milestone N hit | `h_coin_balance += REFERRAL_MILESTONE_REWARD_HCOIN` | `referral_milestone` |
| Audit row | `ReferralMilestoneReward(user, milestone=N, amount, transaction)` | — |
| Push | `referral_milestone` WS event + `balance_update` | — |
| Notify | "You hit N referrals and earned 1 H Coins." | — |

#### Stats endpoint

`GET /api/v1/referrals/stats/` returns:

```json
{
  "l1Count": 12,
  "l2Count": 4,
  "qualifiedCount": 7,
  "pendingDepositCount": 5,
  "milestone": {
    "size": 5,
    "rewardHcoin": "1",
    "milestonesPaid": 1,
    "totalRewardEarnedHcoin": "1",
    "nextMilestoneAt": 10,
    "qualifiedUntilNext": 3,
    "progressPercent": 40.0,
    "qualifyingRule": "Only invited users with at least one completed deposit count toward milestone rewards."
  }
}
```

---

## 6. Trade Bots

Two flavours, configurable via env:

| Knob | Basic default | Expert default |
|---|---|---|
| Fee % | 3 % | 5 % |
| Duration | 24 h (86 400 s) | 48 h (172 800 s) |
| Profit range | 2 – 4 % | 6 – 9 % |

Both percentages are computed against the **balance at activation time** —
not at completion. So if you activate Basic with 100 H, the system always
takes 3 H now and pays you between 2 H and 4 H later, regardless of what
the balance is when the bot finishes.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/api/v1/trade/` | Bot config + active session (single round-trip) |
| `POST` | `/api/v1/trade/activate/` | Start a bot |
| `GET`  | `/api/v1/trade/sessions/` | Paginated history |
| `GET`  | `/api/v1/trade/sessions/<id>/` | Detail |

### Activation flow

1. `SELECT FOR UPDATE` on the wallet — serializes balance writes.
2. Reject if any `BotSession.status="active"` exists for the user. This is
   also enforced by `UniqueConstraint(fields=["user"], condition=Q(status="active"))`
   so even a race can't create two active sessions.
3. Reject if `balance × fee_percent / 100 ≤ 0` (effectively: balance is
   too small).
4. Reject if fee > balance.
5. Debit the wallet, create `Transaction(type=bot_fee, status=completed)`.
6. Create the `BotSession` snapshot with the balance, fee, duration, and
   profit range at activation time.
7. Schedule `complete_bot_session.apply_async(args=[id], countdown=duration)`
   on Celery.
8. Push `bot_activated` + `balance_update` WebSocket events.

### Completion flow

When the Celery countdown fires (or when the periodic
`reconcile_overdue_bot_sessions` task picks up a missed one), the
`complete_bot_session_now(session_id)` service runs:

1. `SELECT FOR UPDATE skip_locked` on the session.
2. Idempotent — no-op if status isn't active.
3. Random profit % within `[profit_min_percent, profit_max_percent]` in
   0.01 % increments.
4. `profit_amount = balance_at_start × profit_percent / 100`.
5. `SELECT FOR UPDATE` on wallet, `h_coin_balance += profit_amount`.
6. Create `Transaction(type=bot_profit, status=completed)`.
7. Flip session to `completed`, populate `profit_percent`,
   `profit_amount_hcoin`, `completed_at`, `profit_transaction`.
8. Push `bot_completed` + `balance_update` WebSocket events.
9. Notify: "You earned X H Coins (Y % profit) from your trading bot."

### Safety nets

* The Celery countdown is primary. If Redis or the worker drops the
  task, the active session would sit forever.
* `reconcile_overdue_bot_sessions()` is a Celery task that scans for
  `status=active AND completes_at <= now()` sessions and dispatches a
  completion for each. Wire into `celery_beat` to run every minute.
* Manual one-shot from the shell:
  ```bash
  docker compose exec django python -c "
  from trade.tasks import reconcile_overdue_bot_sessions
  print(reconcile_overdue_bot_sessions())
  "
  ```

### Balance impact

| Step | Effect | Tx Type |
|---|---|---|
| Activate | `h_coin_balance -= balance × fee_percent / 100` | `bot_fee` |
| Complete | `h_coin_balance += balance_at_start × random_profit_percent / 100` | `bot_profit` |

The fee is **non-refundable** even if the bot is later force-cancelled
(no public cancel endpoint exists yet). All bot transactions appear in
the wallet's transaction feed alongside deposits/withdrawals.

---

## 7. Full balance-change cheat sheet

Every code path that can move `h_coin_balance` or `usdt_balance`, in one place:

| Trigger | Direction | Field affected | Tx Type recorded | Notes |
|---|---|---|---|---|
| Deposit confirmed (first or later) | + | `usdt_balance` | `deposit` | Also flips `has_completed_deposit` on first deposit, which fires `on_deposit_completed` → milestone recheck |
| Withdraw initiated | − | `h_coin_balance` | `withdraw` (pending) | Fee taken from USDT side |
| Withdraw failed | + | `h_coin_balance` (refund) | `withdraw` (failed) | Auto-refund inside atomic block |
| Reward cycle claim | + | `h_coin_balance` | `reward` | Amount snapshotted at activation; cycle cleared |
| Referral commission (L1) | + | inviter's `h_coin_balance` | `commission` (level=1) | 5 % of referee's claimed reward |
| Referral commission (L2) | + | grand-inviter's `h_coin_balance` | `commission` (level=2) | 3 % of referee's claimed reward |
| Referral milestone hit | + | `h_coin_balance` | `referral_milestone` | Triggered by L1's first deposit; idempotent per milestone |
| Bot activation | − | `h_coin_balance` | `bot_fee` | 3 % / 5 % depending on bot |
| Bot completion | + | `h_coin_balance` | `bot_profit` | Random within configured range |
| Admin force-complete deposit | + | `usdt_balance` | `deposit` (completed) | Same as the verify path, also triggers `on_deposit_completed` |

There are **no other writes** to `h_coin_balance` or `usdt_balance`
anywhere in the codebase. Any balance discrepancy must be traceable to one
of the rows above.

---

## 8. Idempotency, locking, and race-safety

The system uses three layers of defense against duplicate / racing writes:

1. **`Idempotency-Key` HTTP header → unique constraint on `(user, idempotency_key)`**
   on the Transaction table. Repeated POSTs to deposit/withdraw/claim
   return the existing row instead of creating a second one.
2. **`SELECT FOR UPDATE` on the wallet row** at every credit/debit. Two
   parallel requests serialize through the database lock so balance reads
   are always consistent.
3. **Domain-specific unique constraints**:
   * `ReferralMilestoneReward(user, milestone)` — no double milestone pay.
   * `BotSession(user, status='active')` partial unique — no two
     simultaneous bots per user.
   * `Referral(inviter, invited_user, level)` — no double-count of
     the same referral.
   * `Transaction.tx_hash` — unique when set (no double-credit of the
     same on-chain deposit).

Every credit also writes a row to `core.audit.AuditLog` via the
`log_audit()` helper, so even a balance change made through the Django
admin is traceable.

---

## 9. Notifications & WebSocket events

A balance change typically fires both a persistent `Notification` row
(visible at the bell-icon dropdown) and a transient WebSocket event for the
SPA to react in real time.

| Trigger | Notification type | WebSocket event |
|---|---|---|
| Deposit confirmed | `deposit` | `transaction_update`, `balance_update` |
| Withdrawal sent | `withdraw` | `transaction_update` |
| Reward cycle activated | (none) | `balance_update` |
| Reward cycle claimed | (none) | `balance_update` |
| L1/L2 commission earned | `commission` | `commission_received`, `balance_update` |
| Referral qualified (1st deposit) | `referral_qualified` | `referral_qualified` |
| Referral milestone hit | `referral_milestone` | `referral_milestone`, `balance_update` |
| Bot activated | (none — UI shows the active card) | `bot_activated`, `balance_update` |
| Bot completed | `bot_complete` | `bot_completed`, `balance_update` |

`Notification` rows are paginated via `/api/v1/notifications/` and an
unread count is exposed at `/api/v1/notifications/unread-count/`.

---

## 10. Throttling

DRF throttles on the auth-sensitive endpoints (configurable via env):

| Endpoint | Default | Env override |
|---|---|---|
| `POST /auth/register/` | 5/min | `THROTTLE_REGISTER_RATE` |
| `POST /auth/login/` | 10/min | `THROTTLE_LOGIN_RATE` |
| `POST /auth/forgot-password/` | 3/min | `THROTTLE_FORGOT_PASSWORD_RATE` |
| `POST /wallet/withdraw/` | 3/min | `WithdrawThrottle.rate` (hard-coded) |
| `POST /referrals/validate/` | 20/min | `ValidateInviteThrottle.rate` |

Plus global defaults from `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES`
(300/min user, 60/min anon — looser in dev settings).

---

## 11. Admin reporting

Every model touching the balance has a Django admin registration:

| Model | Admin features |
|---|---|
| `transactions.Transaction` | List with `type`, `status`, `amount_*`, `tx_hash`. Actions: **Approve withdrawals** (queues `process_withdrawal`), **Force-complete deposit** (credits wallet + triggers `on_deposit_completed`). |
| `wallet.Wallet` | Direct edit (use with caution — bypasses audit). |
| `rewards.RewardCycle` | Read-only history of activations and claims. |
| `referrals.Referral` | List with status pipeline + has_deposit boolean. |
| `referrals.ReferralMilestoneReward` | Read-only; **add/delete disabled** so admins can't manually trigger or undo milestone payouts (idempotency protection). |
| `trade.BotSession` | Read-only history; **add disabled** so sessions can only be created via the service path (which atomically deducts the fee). |

---

## 12. Configuration knobs (full reference)

All overridable via `backend/.env`. Listed here with their defaults.

### Economics

```
USDT_PER_HCOIN=10
MIN_DEPOSIT_USDT=10
WITHDRAWAL_FEE_USDT=1
WITHDRAWAL_AUTO_APPROVE=False
```

### Reward cycle

```
REWARD_DURATION_DAYS=15
REWARD_PERCENT=20
REWARD_MIN_HCOIN=1
REWARD_DURATION_HOURS=12       # legacy, no longer used
REWARD_AMOUNT_HCOIN=5          # legacy, no longer used
GLOBAL_CYCLE_DAYS=30           # fallback if GLOBAL_CYCLE_END_DATE unset
GLOBAL_CYCLE_END_DATE=2026-10-01
```

### Referrals

```
REFERRAL_L1_COMMISSION_PCT=5
REFERRAL_L2_COMMISSION_PCT=3
REFERRAL_MILESTONE_SIZE=5
REFERRAL_MILESTONE_REWARD_HCOIN=1
```

### Trade bots

```
BOT_BASIC_FEE_PCT=3
BOT_BASIC_DURATION_SECONDS=86400
BOT_BASIC_PROFIT_MIN_PCT=2
BOT_BASIC_PROFIT_MAX_PCT=4

BOT_EXPERT_FEE_PCT=5
BOT_EXPERT_DURATION_SECONDS=172800
BOT_EXPERT_PROFIT_MIN_PCT=6
BOT_EXPERT_PROFIT_MAX_PCT=9
```

For local testing, shrink the durations to single-digit seconds:

```
BOT_BASIC_DURATION_SECONDS=60
BOT_EXPERT_DURATION_SECONDS=120
```

then `docker compose up -d --force-recreate django celery celery_beat daphne`.

### Throttling (dev: bumped)

```
THROTTLE_REGISTER_RATE=200/min
THROTTLE_LOGIN_RATE=200/min
THROTTLE_FORGOT_PASSWORD_RATE=20/min
```

---

## 13. Worked example — one user from signup to first bot completion

Assume defaults throughout. User `alice@example.com` registers using
`bob@example.com`'s invite code.

| Step | Alice | Bob | Side effect |
|---|---|---|---|
| Alice registers with Bob's code | balance 0 H | balance 0 H | `Referral(inviter=Bob, invited_user=Alice, level=1)` created |
| Alice deposits 50 USDT (TRC20) | usdt_balance += 50 | unchanged | `Transaction(deposit, 50 USDT)`, `has_completed_deposit=True` for Alice |
| Backend triggers `on_deposit_completed(Alice)` | unchanged | unchanged | Bob now has 1 qualified referral (but not yet a milestone — needs 5) |
| Alice's friends 2–5 do the same | unchanged | balance 0 H | Bob now has 5 qualified referrals |
| (On the 5th deposit) Bob hits milestone 5 | unchanged | balance += 1 H | `Transaction(referral_milestone, 1 H, completed)`, `ReferralMilestoneReward(user=Bob, milestone=5, amount=1)` |
| Bob activates the Basic bot with his 1 H | unchanged | balance 0.97 H, fee row | `Transaction(bot_fee, 0.03 H, completed)`, `BotSession(active, basic)` |
| 24h later, bot completes (random 3.2% profit) | unchanged | balance 1.002 H | `Transaction(bot_profit, ~0.032 H, completed)` |
| Bob activates a 15-day reward cycle | unchanged | balance 1.002 H | `RewardCycle(active, snapshot=0.2 H, ends_at=now+15d)` |
| 15 days later, Bob claims | unchanged | balance ≈ 1.20 H | `Transaction(reward, 0.2 H)`. `distribute_commission(Bob, 0.2)` runs but Bob has no L1 inviter so no commission pays out. |

This is the full economic loop. Every row in the right-most column is
auditable from the Transaction table.

---

## 14. Where to find the code

| Concern | File |
|---|---|
| Deposit endpoints | `backend/wallet/views.py` |
| Deposit verification | `backend/transactions/tasks.py::verify_deposit` |
| Withdrawal endpoints | `backend/wallet/views.py` |
| Withdrawal processing | `backend/transactions/tasks.py::process_withdrawal` |
| Reward cycle | `backend/rewards/views.py`, `backend/rewards/models.py` |
| Referral graph | `backend/referrals/models.py` |
| Qualification helpers | `backend/referrals/models.py::ReferralQuerySet` |
| Commissions | `backend/referrals/services.py::distribute_commission` |
| Milestones | `backend/referrals/services.py::pay_referral_milestones`, `on_deposit_completed` |
| Bots | `backend/trade/` (models, services, tasks, views) |
| Settings | `backend/core/settings/base.py` |
| Reference config | `backend/reference/views.py::PlatformConfigView` |

---

*Generated for the TokenVault codebase as of the May 2026 state. Update this
document whenever a new balance-affecting code path is added.*
