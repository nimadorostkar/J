# === FILE: backend/payments/__init__.py ===
"""Crypto payment gateway: USDT TRC20 + ERC20 deposits and withdrawals.

Architecture
────────────
* `payments.gateway` — chain-specific clients (Tron, Ethereum). Each
  exposes the same interface: get_chain_height(), get_confirmations(),
  get_transfer(tx_hash), list_incoming_transfers(since), send_usdt(...).
* `payments.services` — high-level operations that wrap the gateway and
  the DB: credit_deposit_on_confirmation, broadcast_withdrawal,
  reconcile_pending_deposits, refund_failed_withdrawal.
* `payments.tasks` — Celery tasks: scan_master_wallet (poll for inbound
  USDT) and poll_pending_confirmations.
* `payments.models.GatewayCursor` — persisted scanner position so the
  poller can resume after restarts without re-scanning the chain.

All real-key + RPC calls are gated behind settings.GATEWAY_DRY_RUN so
local dev / CI never burn gas.
"""

default_app_config = "payments.apps.PaymentsConfig"
