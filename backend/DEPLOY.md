# Deploying the Crypto Payment Gateway

Your stack: docker-compose on a VPS, `django` + `daphne` + `celery` +
`celery_beat` + `postgres` + `redis` + `nginx`.

Below is the exact end-to-end runbook. Run **everything from your Mac
terminal** unless a step explicitly says *on the VPS*.

---

## 1. Merge the cleanup commit locally + push to GitHub (your Mac)

A side branch `claude/gateway-cleanup` has been pushed to your local
repo. Clear the stale git lock, fast-forward `main`, and push:

```bash
cd /Users/nima/Projects/J

# 1. Clear the stale git lock (from a previous sandbox run).
rm -f .git/index.lock

# 2. Fast-forward main with the cleanup commit and push to GitHub.
git fetch . claude/gateway-cleanup:claude-tmp
git checkout main
git merge --ff-only claude-tmp
git branch -D claude-tmp
git branch -D claude/gateway-cleanup  # optional cleanup of the side branch
git push origin main
```

If `git push` asks for credentials and you don't have a token set up:

```bash
# One-time: install GitHub CLI and auth
brew install gh
gh auth login           # pick HTTPS, browser auth — easiest
git push origin main
```

---

## 2. Pull, rebuild, and migrate (on the VPS)

SSH to your VPS and run, from the `backend/` directory:

```bash
cd /path/to/J/backend          # wherever you checked the repo out
git pull origin main
docker compose build django daphne celery celery_beat
docker compose up -d            # picks up rebuilt images
docker compose exec django python manage.py migrate --noinput
docker compose logs -f celery_beat | head -30
```

You should see the three new beat schedules log themselves:
`scan_master_wallet`, `poll_pending_deposits`, `poll_pending_withdrawals`.

---

## 3. Configure the live gateway env vars (on the VPS)

Edit `backend/.env` and **add or update** these:

```env
# ── Crypto payment gateway ──────────────────────────────────────────
# MUST be False to actually broadcast on-chain. Default is True.
GATEWAY_DRY_RUN=False

# Public master hot wallet addresses (one per chain).
USDT_TRC20_WALLET=Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
USDT_ERC20_WALLET=0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Private keys — generate offline, NEVER commit to git.
TRON_HOT_WALLET_PRIVATE_KEY=64-hex-no-0x-prefix
ETHEREUM_HOT_WALLET_PRIVATE_KEY=0x64-hex

# RPC endpoints.
TRON_FULLNODE_URL=https://api.trongrid.io
TRON_API_KEY=your-trongrid-pro-key
ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/<project-id>
ETHEREUM_API_KEY=your-etherscan-key
ETHERSCAN_API_URL=https://api.etherscan.io/api

# Network / contract.
TRON_NETWORK=mainnet
ETHEREUM_NETWORK=mainnet
USDT_TRC20_CONTRACT=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
USDT_ERC20_CONTRACT=0xdAC17F958D2ee523a2206206994597C13D831ec7

# Confirmation depth before crediting a deposit.
MIN_CONFIRMATIONS_TRC20=19
MIN_CONFIRMATIONS_ERC20=12

# Withdrawal safety rails.
MIN_WITHDRAWAL_USDT=5
MAX_WITHDRAWAL_USDT=10000
DAILY_WITHDRAWAL_LIMIT_USDT=50000
WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT=1000

# Existing flag — only auto-broadcast withdrawals below the review
# threshold. Above the threshold an admin must approve via the admin
# REST endpoint or Django admin.
WITHDRAWAL_AUTO_APPROVE=True
```

Then install the on-chain signing libs (only needed because
`GATEWAY_DRY_RUN=False`):

```bash
# Uncomment the bottom of backend/requirements.txt:
#   tronpy>=0.4
#   web3>=6.0
#   eth-account>=0.10
sed -i 's|# tronpy|tronpy|;s|# web3|web3|;s|# eth-account|eth-account|' backend/requirements.txt
docker compose build django daphne celery celery_beat
docker compose up -d
```

---

## 4. Smoke test (on the VPS, then your Mac)

```bash
# Health
curl -s http://localhost:8000/api/v1/health/

# Gateway status (needs an admin JWT in the Authorization header)
TOKEN=<your admin access token>
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/payments/admin/gateway/status/ | jq .
```

Expected JSON contains:

```json
{
  "dryRun": false,
  "pendingDeposits": 0,
  "pendingReviewWithdrawals": 0,
  "broadcastWithdrawals": 0,
  "networks": {
    "TRC20": {"rpcReachable": true, "chainHeight": 123456789, ...},
    "ERC20": {"rpcReachable": true, "chainHeight": 19000000, ...}
  }
}
```

If `rpcReachable: false` — the RPC URL or API key is wrong.

---

## 5. End-to-end test with a real $1 deposit

1. From your personal Tron wallet, send **1 USDT** to `USDT_TRC20_WALLET`.
2. Wait ~1 minute. The `scan_master_wallet` beat task picks it up.
   The transfer appears in **Django admin → Payments → Gateway event logs**
   (matched user blank if you haven't linked a `wallet.DepositAddress`
   row for the sender).
3. Link the sender to a user (or skip — for tx_hash-initiated deposits
   the API submits the hash directly):
   ```sql
   INSERT INTO wallet_depositaddress (network, address, is_active, user_id, created_at)
   VALUES ('TRC20', 'TYourSenderAddress', true, <user_id>, NOW());
   ```
4. The `poll_pending_deposits` task will credit once 19 confirmations land
   (~1 minute on Tron). Watch in **Django admin → Transactions** — status
   flips from `pending` → `completed`.

---

## 6. End-to-end test with a small withdrawal

1. As a regular user, hit `POST /api/v1/wallet/withdraw/` with a small
   amount (below `WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT`).
2. Auto-broadcast kicks in; status becomes `processing` once the
   `process_withdrawal` Celery task runs.
3. `poll_pending_withdrawals` flips it to `completed` once 12
   confirmations land.
4. Verify the tx_hash on TronScan / Etherscan.

For amounts above the threshold:
```bash
# List the queue
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/payments/admin/withdrawals/pending/

# Approve
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/payments/admin/withdrawals/<uuid>/approve/

# Reject + refund
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"KYC pending"}' \
  http://localhost:8000/api/v1/payments/admin/withdrawals/<uuid>/reject/
```

---

## 7. Rollback (if anything goes sideways)

```bash
# On the VPS:
cd /path/to/J/backend
git revert ae865f4 b9cd95f --no-edit   # revert cleanup + the gateway commit
docker compose build django daphne celery celery_beat
docker compose up -d
docker compose exec django python manage.py migrate transactions zero || true
```

Or, faster: set `GATEWAY_DRY_RUN=True` in `.env` and restart — no real
broadcasts will happen and the system behaves like before, while you
debug.

---

## 8. Monitoring

- **Django admin → Payments → Gateway cursors**: last-scanned block + error
  count per chain. Set up an alert if `error_count > 5` or
  `last_scanned_at` is older than ~10 minutes.
- **`/api/v1/payments/admin/gateway/status/`**: queryable for a status
  dashboard.
- **Hot wallet balance**: tail TronScan / Etherscan in case payouts
  drain the master wallet. Set a low-water-mark alert in your ops
  pipeline.
