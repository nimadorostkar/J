# === FILE: backend/payments/gateway/base.py ===
"""Abstract gateway client.

Every chain-specific client (Tron, Ethereum, ...) MUST implement this
interface so the rest of the codebase can swap chains without
re-writing service / task code.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional


class GatewayError(Exception):
    """Base error for gateway operations.

    Carry an optional `retryable` flag so callers (Celery tasks) can
    decide between exponential backoff and a hard fail.
    """

    def __init__(self, message: str = "", *, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class InsufficientGas(GatewayError):
    """Hot wallet doesn't have enough native coin to pay gas/bandwidth."""

    def __init__(self, message: str = "Hot wallet has insufficient gas"):
        super().__init__(message, retryable=False)


class ChainNotConfirmed(GatewayError):
    """Transaction not yet confirmed at the required depth."""

    def __init__(self, message: str = "Transaction not yet confirmed"):
        super().__init__(message, retryable=True)


@dataclass(frozen=True)
class ChainTransfer:
    """Normalized representation of a single USDT transfer event.

    All amounts are USDT (not raw token units). `confirmations` may be 0
    if the tx is in the mempool / unconfirmed block.
    """

    tx_hash: str
    log_index: int
    block_number: int
    from_address: str
    to_address: str
    amount_usdt: Decimal
    confirmations: int
    network: str

    @property
    def is_confirmed(self) -> bool:
        return self.confirmations > 0


class BaseGatewayClient(abc.ABC):
    """Thin port to a single blockchain. Subclasses MUST implement all
    abstract methods."""

    #: Network code — one of ``"TRC20"`` / ``"ERC20"``.
    NETWORK: str = ""

    #: USDT token decimals on this chain.
    DECIMALS: int = 6

    def __init__(self, *, dry_run: bool = True, timeout: int = 15):
        self.dry_run = dry_run
        self.timeout = timeout

    # ── Read-only methods ────────────────────────────────────────────
    @abc.abstractmethod
    def get_chain_height(self) -> int:
        """Return the current block height of this chain."""

    @abc.abstractmethod
    def get_transfer(self, tx_hash: str) -> Optional[ChainTransfer]:
        """Look up a single USDT transfer by tx hash.

        Returns ``None`` if the tx doesn't exist OR isn't a USDT
        transfer to/from the master wallet.
        """

    @abc.abstractmethod
    def list_incoming_transfers(
        self, *, address: str, from_block: int = 0, limit: int = 50
    ) -> Iterable[ChainTransfer]:
        """List USDT transfers *into* ``address`` newer than
        ``from_block``."""

    def get_confirmations(self, tx_hash: str) -> int:
        """Return current confirmation count for ``tx_hash`` (0 if
        unknown / mempool)."""
        transfer = self.get_transfer(tx_hash)
        return transfer.confirmations if transfer else 0

    # ── Write-only methods ───────────────────────────────────────────
    @abc.abstractmethod
    def send_usdt(self, *, to_address: str, amount_usdt: Decimal) -> str:
        """Sign + broadcast a USDT transfer from the master hot wallet.

        Returns the tx_hash. Raises GatewayError on failure.
        """

    # ── Helpers ──────────────────────────────────────────────────────
    def _to_token_units(self, amount_usdt: Decimal) -> int:
        """USDT (human) → smallest token unit (int)."""
        scaled = Decimal(amount_usdt) * (Decimal(10) ** self.DECIMALS)
        # Floor to avoid sending fractional units we can't represent.
        return int(scaled.quantize(Decimal("1")))

    def _from_token_units(self, raw: int) -> Decimal:
        """Smallest token unit → human-readable USDT Decimal."""
        return (Decimal(raw) / (Decimal(10) ** self.DECIMALS)).quantize(
            Decimal("0.00000001")
        )
