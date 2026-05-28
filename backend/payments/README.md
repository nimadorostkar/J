# Crypto Payment Gateway

Custodial USDT gateway for TokenVault. One **master hot wallet** per chain
holds the funds; per-user balances live in the DB (`wallet.Wallet`).

## Architecture

```
                 ┌──────────────────────────────────────────┐
                 │             Master Hot Wallet            │
                 │   TRC20 addr · ERC20 addr (USDT only)    │
                 └────────────┬─────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
   ┌──────────▼─────────┐         ┌───────────▼─────────┐
   │   Deposit flow     │         │   Withdraw flow     │
   │                    │         │                     │
   │  Customer sends    │         │  User → API request │
   │  USDT to master    │         │  → debit DB balance │
   │  ↓                 │         │  → broadcast send_  │
   │  Scanner detects   │         │    usdt() via hot   │
   │  → ingest event    │         │    wallet           │
   │  → create Tx       │         │  → poll conf depth  │
   │  → poll confs      │         │  → mark COMPLETED   │
   │  → credit wallet   │         │                     │
   └────────────────────┘         └─────────────────────┘
```

## Files

| Path | Purpose |
| ---- | ------- |
| `gateway/base.py` | Abstract `BaseGatewayClient` + `ChainTransfer` dataclass. |
| `gateway/tron.py` | TRC20 client (TronGrid + optional tronpy for signing). |
| `gateway/ethereum.py` | ERC20 client (Etherscan + JSON-RPC + optional web3.py). |
| `gateway/__init__.py` | `get_client(network)` factory. |
| `services.py` | DB-aware operations: credit/debit, limits, refunds, idempotency. |
| `tasks.py` | Celery beat: scan, poll confirmations, finalize. |
| `models.py` | `GatewayCursor` (resume scan position), `GatewayEventLog`. |
| `views.py` + `urls.py` | Admin REST endpoints for the manual-review queue. |
| `admin.py` | Django admin for cursors, events, scan-now buttons. |

## Environment / settings

Required in production (`backend/core/settings/base.py`):

```env
GATEWAY_DRY_RUN=False                # MUST be False to actually broadcast
USDT_TRC20_WALLET=Txxxxxxx...        # master hot wallet TRC20 address
USDT_ERC20_WALLET=0xxxxx...          # master hot wallet ERC20 address
TRON_HOT_WALLET_PRIVATE_KEY=64hex    # signs withdrawals
ETHEREUM_HOT_WALLET_PRIVATE_KEY=0x.. # signs withdrawals
TRON_FULLNODE_URL=https://api.trongrid.io
ETHEREUM_RPC_URL=https://...         # Infura/Alchemy/Quicknode
TRON_API_KEY=<TronGrid key>
ETHEREUM_API_KEY=<Etherscan key>
MIN_CONFIRMATIONS_TRC20=19
MIN_CONFIRMATIONS_ERC20=12
MAX_WITHDRAWAL_USDT=10000
DAILY_WITHDRAWAL_LIMIT_USDT=50000
WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT=1000
WITHDRAWAL_AUTO_APPROVE=True         # auto-broadcast below threshold
```

When `GATEWAY_DRY_RUN=True` (the default) no real chain calls happen:
`send_usdt` returns a `simulated-...` tx hash, `get_transfer` accepts
those hashes as "fully confirmed". Useful for local dev and CI.

## Deposit flow

1. Frontend calls `POST /api/v1/wallet/deposit/` with `{amountUsdt, network, txHash}`
   *or* the user just sends USDT directly to the master wallet.
2. **If the user submitted a tx_hash:** `verify_deposit` Celery task polls the
   chain. When confirmations >= `MIN_CONFIRMATIONS_<NET>`, the credit happens
   atomically in `services.confirm_and_credit_deposit`.
3. **If no tx_hash:** `scan_master_wallet` (beat, every 2 min) lists
   recent inbound USDT, ingests them into `GatewayEventLog`, and
   matches the sender to a user via `wallet.DepositAddress`. Matched
   transfers auto-create a pending `Transaction` which the
   `poll_pending_deposits` task then credits when confirmed.

## Withdrawal flow

1. Frontend calls `POST /api/v1/wallet/withdraw/` with `{network, address, tokens}`.
2. Server validates eligibility (existing rules + new per-tx / daily caps),
   debits H Coins, and creates a `pending` Transaction. If
   `amount_usdt >= WITHDRAWAL_ADMIN_REVIEW_THRESHOLD_USDT` the transaction is
   flagged `requires_admin_review=True` and NOT broadcast automatically.
3. Admin reviews via Django admin **or** `POST /api/v1/payments/admin/withdrawals/<id>/approve/`.
4. `process_withdrawal` Celery task calls `payments.services.broadcast_withdrawal`,
   which signs+broadcasts via the gateway client and stores the on-chain tx_hash.
5. `poll_pending_withdrawals` (beat, every 1 min) polls confirmations and flips
   the status to `completed`.
6. On hard-failure (insufficient gas / RPC permanent error / bad address) the
   user's H Coin balance is automatically **refunded** in the same DB
   transaction and the withdrawal is marked `failed`.

## Admin endpoints (require staff JWT)

```http
GET  /api/v1/payments/admin/gateway/status/
GET  /api/v1/payments/admin/withdrawals/pending/
POST /api/v1/payments/admin/withdrawals/<uuid>/approve/
POST /api/v1/payments/admin/withdrawals/<uuid>/reject/      body: {"reason": "..."}
```

The Django admin has equivalent buttons and an extra "Scan now" action
under *Payments → Gateway cursors*.

## Going live checklist

1. Generate hot-wallet private keys offline.
2. Fund both master wallets with USDT for outbound payouts + native gas
   (TRX for Tron, ETH for Ethereum) for fees.
3. Set the env vars above. `GATEWAY_DRY_RUN=False` LAST.
4. Install signing deps in your image:
   `pip install tronpy web3 eth-account`.
5. Restart celery workers + beat so the new tasks run.
6. Send a 1 USDT test deposit and watch the dashboard at
   `/api/v1/payments/admin/gateway/status/`.
7. Try a small test withdrawal under the admin-review threshold to
   confirm auto-broadcast works.
