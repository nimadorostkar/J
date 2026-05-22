# TokenVault Backend

Production-ready Django 5 backend for **TokenVault** — a gamified USDT / H Coin wallet platform with mandatory invite-code registration, two-level referral commission, timed reward cycles, gated withdrawals, and live WebSocket updates.

## Stack

- Python 3.12 · Django 5 · Django REST Framework 3
- PostgreSQL 16 · Redis 7
- Celery 5 (worker + beat)
- Django Channels + Daphne (WebSocket)
- JWT auth (rotating refresh + blacklist)
- Docker / Docker Compose / Nginx
- S3 (avatars) via `django-storages`
- Swagger / OpenAPI docs at `/api/docs/`

## Quick start (Docker)

```bash
cp .env.example .env
# edit secrets in .env, then:
docker compose up --build
```

Services started:

| Service       | Port | Purpose                              |
|---------------|------|--------------------------------------|
| nginx         | 80   | HTTP / WebSocket reverse proxy       |
| django        | 8000 | Gunicorn (REST)                      |
| daphne        | 9000 | ASGI server (WebSocket)              |
| celery        | —    | Background worker                    |
| celery_beat   | —    | Scheduled-task scheduler             |
| postgres      | 5432 | Primary database                     |
| redis         | 6379 | Cache, Celery broker, channel layer  |

API root: `http://localhost/api/v1/`  · Docs: `http://localhost/api/docs/`

## First-time setup

```bash
docker compose exec django python manage.py migrate
docker compose exec django python manage.py loaddata fixtures/countries.json fixtures/dial_codes.json
docker compose exec django python manage.py createsuperuser
```

A `Wallet` row is auto-created via a `post_save` signal whenever a `User` is created — no manual provisioning needed.

## Local development (without Docker)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_ENV=dev
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
# WebSockets (separate terminal):
daphne -b 0.0.0.0 -p 9000 core.asgi:application
# Background work:
celery -A core worker -l info
celery -A core beat -l info
```

## Environment variables (.env)

See `.env.example` for the full list. Critical ones:

| Var | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key — rotate before prod. |
| `DATABASE_URL` | Postgres DSN. |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CHANNEL_LAYERS_URL` | Redis connections. |
| `JWT_ACCESS_TTL_MINUTES` (15) / `JWT_REFRESH_TTL_DAYS` (7) | Token lifetimes. |
| `USDT_PER_HCOIN` (10) | Conversion rate. |
| `MIN_DEPOSIT_USDT` (10) / `WITHDRAWAL_FEE_USDT` (1) | Economics. |
| `WITHDRAWAL_AUTO_APPROVE` (False) | Auto-queue withdrawals via Celery vs. require admin approval. |
| `REWARD_DURATION_HOURS` (12) / `REWARD_AMOUNT_HCOIN` (5) | Reward cycle config. |
| `GLOBAL_CYCLE_DAYS` (30) | Shared home-tab countdown. |
| `REFERRAL_L1_COMMISSION_PCT` (5) / `REFERRAL_L2_COMMISSION_PCT` (3) | Commission rates. |
| `FIELD_ENCRYPTION_KEY` | Fernet key for at-rest encryption of withdrawal addresses. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `BLOCKCHAIN_WEBHOOK_SECRET` | HMAC secret verified on `/api/v1/webhooks/blockchain/`. |
| `USDT_TRC20_WALLET` / `USDT_ERC20_WALLET` | Treasury deposit addresses surfaced to users. |
| `AWS_*` + `USE_S3=True` | S3 storage for avatars. |

## API overview

All endpoints prefixed `/api/v1/`. Auth uses `Authorization: Bearer <accessToken>`.

### Auth (`/auth/...`)
- `POST register/` — `{firstName, lastName, email, password, inviteCode}` · **inviteCode required**
- `POST login/` / `POST logout/` / `POST refresh/`
- `POST forgot-password/` / `POST reset-password/` / `POST verify-email/`

### Profile (`/users/me/...`)
- `GET|PATCH /` profile · `POST avatar/` · `POST password/` · `GET status/`

### Wallet (`/wallet/...`)
- `GET /` balances and cycle status
- `GET transactions/?type=commission&limit=20` cursor-paginated history
- `GET networks/` · `GET deposit-address/?network=TRC20`
- `POST deposit/` (idempotency-key header) · `GET deposit/<id>/`
- `POST withdraw/` (gated — see below) · `GET withdraw/<id>/`
- `GET withdraw/eligibility/` returns `{eligible, missingConditions[], details}`

### Reward (`/reward/...`)
- `GET cycle/` · `POST cycle/activate/` · `POST cycle/claim/`
- `GET global-cycle/`

### Referrals (`/referrals/...`)
- `GET code/` · `GET network/` · `GET stats/` · `POST validate/`

### Notifications (`/notifications/...`)
- `GET /` · `GET unread-count/` · `PATCH <id>/read/` · `POST read-all/`

### Support · Reference · Stubs
- `/support/faqs/` `/support/tickets/`
- `/reference/countries/` `/reference/dial-codes/` `/reference/config/`
- `/tournaments/` and `/lucky-spin/` return **501 Coming Soon**

### Webhooks
- `POST /api/v1/webhooks/blockchain/` — provider posts `{tx_hash, ...}` signed with `X-Webhook-Signature` HMAC.

## Mandatory invite-code registration

`POST auth/register/` requires `inviteCode`. The serializer:

1. Validates the format (8 chars, alphanumeric, case-insensitive).
2. Resolves it to a `User` (404 → `400 INVALID_INVITE_CODE`).
3. Sets `referred_by` and creates `Referral(level=1)`.
4. If the inviter was itself referred, creates `Referral(level=2)` for the grand-inviter.
5. Sets `wallet.has_referral=True` on the inviter (and the grand-inviter when applicable).

All five steps run in **one atomic transaction with user creation** — no orphaned referrals.

## Withdrawal eligibility gate

`POST wallet/withdraw/` returns **HTTP 403** with body:

```json
{
  "code": "WITHDRAWAL_LOCKED",
  "message": "Withdrawal requires completing both conditions.",
  "missingConditions": ["initial_deposit", "referral"],
  "details": {
    "initial_deposit": {"met": false, "description": "..."},
    "referral":        {"met": false, "description": "..."}
  }
}
```

Both flags are **cached booleans** on the `Wallet` row (`has_completed_deposit`, `has_referral`) — O(1) under load, not live counts. Use `GET wallet/withdraw/eligibility/` to drive the UI without attempting a withdrawal.

## Referral commission engine

Lives in `referrals/services.py` as `distribute_commission(user, profit_hcoin)`. It is **synchronous** and must be called inside the same `@transaction.atomic` block as the profit credit (see `rewards/views.py::ClaimCycleView`). For each profit event:

- L1 inviter gets `profit × REFERRAL_L1_COMMISSION_PCT / 100`
- L2 inviter (if any) gets `profit × REFERRAL_L2_COMMISSION_PCT / 100`

For each payout we:

1. `select_for_update()` the `Referral` row and the inviter's `Wallet`.
2. Credit H Coins to inviter's wallet.
3. Create a `Transaction(type="commission", commission_level=…, commission_rate=…, commission_from_user=user)` — the rate is snapshotted so future config changes don't alter history.
4. Increment `Referral.total_commission_earned_hcoin`.
5. Queue an in-app notification and push `commission_received` + `balance_update` over WebSocket.

If any step throws the entire atomic block rolls back — **inviters are always paid or no one is paid**.

## WebSocket (`/ws/wallet/?token=<accessToken>`)

`WalletConsumer` joins group `wallet_{user_id}` and emits:

```json
{"type": "balance_update", "hCoins": "12.34", "usdtBalance": "100"}
{"type": "reward_claimable"}
{"type": "transaction_update", "id": "...", "status": "completed"}
{"type": "notification", "title": "...", "body": "..."}
{"type": "commission_received", "amount": "0.25", "level": 1, "fromUser": {...}}
```

## Celery tasks

| Task | Schedule | Purpose |
|---|---|---|
| `transactions.tasks.verify_deposit` | on-demand | On-chain verification → credit wallet |
| `transactions.tasks.process_withdrawal` | on-demand | Send blockchain transfer |
| `transactions.tasks.expire_stale_deposits` | hourly | Mark >24h pending deposits as failed |
| `rewards.tasks.check_reward_cycles` | every 60s | Promote ACTIVE → CLAIMABLE |
| `rewards.tasks.rotate_global_cycle` | daily 00:05 | Roll the 30-day shared countdown |
| `notifications.tasks.send_notification` | on-demand | Create row + push via Channels |

All financial tasks use `acks_late=True` + retry.

## Financial safety rules

1. Money fields are `DecimalField(max_digits=18, decimal_places=8)`.
2. All wallet mutations use `transaction.atomic` + `select_for_update`.
3. Frontend amounts are re-validated server-side.
4. Idempotency keys (header `Idempotency-Key`) gate deposit/withdraw/claim.
5. Negative-balance guards raise `InsufficientBalance` → HTTP 400.
6. All financial events are written to `AuditLog` before commit.
7. Withdrawal addresses are validated (TRC20 base58 / ERC20 EIP-55) before any DB row is created.
8. Blockchain webhooks verified by HMAC `X-Webhook-Signature`.
9. Hot vs. treasury wallets — surfaced via `USDT_TRC20_WALLET` / `USDT_ERC20_WALLET`; replace the placeholder signer in `process_withdrawal` with your real hot-wallet client.
10. Every Celery financial task is `acks_late=True` with bounded retries.
11. `distribute_commission` runs inside the same atomic block as the original profit credit.
12. Commission rate is **snapshotted** into each commission `Transaction` row.
13. The withdrawal gate reads cached booleans (`wallet.has_completed_deposit`, `wallet.has_referral`) — O(1).
14. Registration rejects missing/invalid invite codes — no user is created without a valid referral chain.

## Admin

- `Transaction` — actions: **Approve withdrawal**, **Force-complete deposit**.
- `Wallet` — action: **Reset reward cycle**.
- `User` — action: **Export to CSV**.
- `Referral` — inline view per user; shows `total_commission_earned_hcoin`.
- `AuditLog` — read-only.

## Project layout

```
backend/
├── core/            # settings (base/dev/prod), urls, celery, asgi, channels auth, audit
├── users/           # User model, auth views, profile, signals (auto-wallet)
├── wallet/          # Wallet model, eligibility gate, deposit/withdraw views, consumer
├── transactions/    # Transaction model, webhooks, Celery tasks
├── referrals/       # Referral model, distribute_commission service
├── rewards/         # RewardCycle / GlobalCycle, claim hook, beat tasks
├── notifications/   # Notification model, send_notification task
├── support/         # FAQ, Ticket, TicketMessage
├── reference/       # Country, DialCode, PlatformConfig (+ fixtures)
├── tournaments/     # stub → 501
├── lucky_spin/      # stub → 501
├── fixtures/        # countries.json, dial_codes.json
├── nginx/nginx.conf
├── docker-compose.yml · Dockerfile · requirements.txt · .env.example · manage.py
```
