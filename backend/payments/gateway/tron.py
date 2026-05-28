# === FILE: backend/payments/gateway/tron.py ===
"""Tron (TRC20-USDT) gateway client.

Two layers:

1. **Read paths** use plain HTTP against TronGrid (no extra runtime
   dependency required). This makes deposit polling work even in a
   minimal container — only `requests` is needed (already in
   requirements.txt).

2. **Write paths** (signing + broadcasting withdrawals) use ``tronpy``
   when it's available. If ``tronpy`` is missing AND we're not in dry
   run, we raise so the operator notices instead of silently dropping
   payouts.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable, Optional

import requests
from django.conf import settings

from .base import BaseGatewayClient, ChainTransfer, GatewayError, InsufficientGas

logger = logging.getLogger("tokenvault")

try:  # pragma: no cover — optional dependency
    from tronpy import Tron  # type: ignore
    from tronpy.keys import PrivateKey  # type: ignore
    from tronpy.providers import HTTPProvider  # type: ignore

    _HAS_TRONPY = True
except Exception:  # pragma: no cover
    _HAS_TRONPY = False


class TronGateway(BaseGatewayClient):
    NETWORK = "TRC20"

    @property
    def DECIMALS(self) -> int:  # type: ignore[override]
        return int(getattr(settings, "USDT_DECIMALS_TRC20", 6))

    # ── config ───────────────────────────────────────────────────────
    @property
    def _api(self) -> str:
        return getattr(settings, "TRON_FULLNODE_URL", "https://api.trongrid.io").rstrip("/")

    @property
    def _contract(self) -> str:
        return getattr(settings, "USDT_TRC20_CONTRACT", "")

    @property
    def _master_address(self) -> str:
        return getattr(settings, "USDT_TRC20_WALLET", "")

    @property
    def _headers(self) -> dict:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        key = getattr(settings, "TRON_API_KEY", "")
        if key:
            h["TRON-PRO-API-KEY"] = key
        return h

    # ── HTTP helpers ─────────────────────────────────────────────────
    def _get(self, path: str, params: dict | None = None) -> dict:
        url = f"{self._api}{path}"
        try:
            r = requests.get(url, params=params or {}, headers=self._headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise GatewayError(f"Tron RPC GET {path} failed: {e}", retryable=True) from e
        if r.status_code >= 500:
            raise GatewayError(f"Tron RPC 5xx ({r.status_code})", retryable=True)
        if not r.ok:
            raise GatewayError(
                f"Tron RPC error {r.status_code}: {r.text[:300]}",
                retryable=r.status_code in (408, 429),
            )
        return r.json() or {}

    def _post(self, path: str, json: dict) -> dict:
        url = f"{self._api}{path}"
        try:
            r = requests.post(url, json=json, headers=self._headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise GatewayError(f"Tron RPC POST {path} failed: {e}", retryable=True) from e
        if not r.ok:
            raise GatewayError(
                f"Tron RPC error {r.status_code}: {r.text[:300]}",
                retryable=r.status_code in (408, 429, 503),
            )
        return r.json() or {}

    # ── BaseGatewayClient implementation ─────────────────────────────
    def get_chain_height(self) -> int:
        data = self._post("/wallet/getnowblock", json={})
        return int(data.get("block_header", {}).get("raw_data", {}).get("number") or 0)

    def get_transfer(self, tx_hash: str) -> Optional[ChainTransfer]:
        if not tx_hash:
            return None
        if self.dry_run and tx_hash.startswith(("simulated-", "manual-")):
            # Local dev convenience: synthetic hashes "exist" with full confirmation.
            return ChainTransfer(
                tx_hash=tx_hash,
                log_index=0,
                block_number=0,
                from_address="",
                to_address=self._master_address,
                amount_usdt=Decimal("0"),
                confirmations=getattr(settings, "MIN_CONFIRMATIONS_TRC20", 19) + 1,
                network=self.NETWORK,
            )

        # TronGrid's "transactioninfo" returns block + receipt;
        # "gettransactionbyid" returns the contract data (i.e. the
        # TRC20 transfer parameters).
        info = self._post("/wallet/gettransactioninfobyid", json={"value": tx_hash})
        if not info:
            return None
        tx = self._post("/wallet/gettransactionbyid", json={"value": tx_hash})
        if not tx:
            return None

        block_number = int(info.get("blockNumber") or 0)
        if block_number == 0:
            return None

        contract = (tx.get("raw_data", {}).get("contract") or [{}])[0]
        params = contract.get("parameter", {}).get("value", {})

        # We only care about TriggerSmartContract calls into the USDT
        # contract. Anything else is not a USDT transfer.
        contract_addr_hex = params.get("contract_address") or ""
        contract_addr = _hex_to_base58(contract_addr_hex) if contract_addr_hex else ""
        if contract_addr.lower() != self._contract.lower():
            return None

        # Decode `transfer(address,uint256)` from the input data.
        from_addr = _hex_to_base58(params.get("owner_address", ""))
        data = params.get("data", "")
        to_addr, amount_raw = _decode_trc20_transfer(data)
        amount_usdt = self._from_token_units(amount_raw)

        height = self.get_chain_height()
        confs = max(0, height - block_number)

        return ChainTransfer(
            tx_hash=tx_hash,
            log_index=0,
            block_number=block_number,
            from_address=from_addr,
            to_address=to_addr,
            amount_usdt=amount_usdt,
            confirmations=confs,
            network=self.NETWORK,
        )

    def list_incoming_transfers(
        self, *, address: str, from_block: int = 0, limit: int = 50
    ) -> Iterable[ChainTransfer]:
        """Walk recent USDT transfers into ``address`` via TronGrid's
        account API. ``from_block`` is a high-water mark — anything at
        or before it is skipped (the scanner persists this in
        GatewayCursor.last_block).
        """
        if not address:
            return []
        path = f"/v1/accounts/{address}/transactions/trc20"
        params = {
            "limit": min(limit, 200),
            "only_to": "true",
            "contract_address": self._contract,
        }
        data = self._get(path, params=params)
        results = []
        height = self.get_chain_height()
        for row in (data.get("data") or []):
            tx_hash = row.get("transaction_id") or ""
            block_number = int(row.get("block_timestamp") or 0)  # ms, not block — we use as monotonic id
            # TronGrid doesn't return block height on this endpoint, only
            # block_timestamp (ms). We use that as the monotonic cursor.
            if block_number and from_block and block_number <= from_block:
                continue
            from_addr = row.get("from") or ""
            to_addr = row.get("to") or ""
            amount_raw = int(row.get("value") or 0)
            amount_usdt = self._from_token_units(amount_raw)

            # We can't get confirmation count cheaply from this endpoint
            # — caller can re-check per-tx with get_transfer() before
            # crediting. For the scanner, we mark confirmations=0 and
            # let the polling stage upgrade it.
            results.append(
                ChainTransfer(
                    tx_hash=tx_hash,
                    log_index=0,
                    block_number=block_number,
                    from_address=from_addr,
                    to_address=to_addr,
                    amount_usdt=amount_usdt,
                    confirmations=0,
                    network=self.NETWORK,
                )
            )
        return results

    def send_usdt(self, *, to_address: str, amount_usdt: Decimal) -> str:
        if self.dry_run:
            simulated = f"simulated-trc20-{abs(hash((to_address, str(amount_usdt))))%(16**16):016x}"
            logger.info(
                "TronGateway dry-run: would send %s USDT to %s — tx=%s",
                amount_usdt, to_address, simulated,
            )
            return simulated

        if not _HAS_TRONPY:
            raise GatewayError(
                "tronpy is required for outbound Tron transfers. Install with `pip install tronpy`.",
                retryable=False,
            )

        pk_hex = getattr(settings, "TRON_HOT_WALLET_PRIVATE_KEY", "")
        if not pk_hex:
            raise GatewayError("TRON_HOT_WALLET_PRIVATE_KEY not configured", retryable=False)
        if not self._contract or not self._master_address:
            raise GatewayError("Tron contract/master wallet not configured", retryable=False)

        try:
            client = Tron(HTTPProvider(self._api, api_key=getattr(settings, "TRON_API_KEY", "") or None))
            priv = PrivateKey(bytes.fromhex(pk_hex))
            contract = client.get_contract(self._contract)
            raw_amount = self._to_token_units(amount_usdt)
            txn = (
                contract.functions.transfer(to_address, raw_amount)
                .with_owner(self._master_address)
                .fee_limit(10_000_000)
                .build()
                .sign(priv)
            )
            result = txn.broadcast().wait()  # blocks ~3-5s for first confirm
            tx_hash = result.get("id") if isinstance(result, dict) else getattr(result, "txid", None) or txn.txid
            if not tx_hash:
                raise GatewayError("Tron broadcast returned no tx_hash", retryable=True)
            return str(tx_hash)
        except GatewayError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "balance" in msg or "energy" in msg or "bandwidth" in msg:
                raise InsufficientGas(str(e)) from e
            raise GatewayError(f"Tron broadcast failed: {e}", retryable=True) from e


# ─── Helpers — TRC20 ABI decoding without web3 / tronpy ─────────────
def _hex_to_base58(hex_addr: str) -> str:
    """Tron addresses are 21 bytes starting with 0x41. base58-check
    encodes them. We accept hex-with-or-without leading 0x41 and return
    the customer-visible "T..." string."""
    if not hex_addr:
        return ""
    raw = bytes.fromhex(hex_addr[2:] if hex_addr.startswith("0x") else hex_addr)
    if len(raw) == 20:
        raw = b"\x41" + raw
    if len(raw) != 21 or raw[0] != 0x41:
        return ""
    try:
        import base58
        return base58.b58encode_check(raw).decode()
    except Exception:  # pragma: no cover
        return ""


def _decode_trc20_transfer(data: str) -> tuple[str, int]:
    """Decode ABI-encoded `transfer(address,uint256)` calldata.

    Layout:
      bytes  0.. 3  selector (0xa9059cbb)
      bytes  4..35  recipient (left-padded 32 bytes — last 20 are addr)
      bytes 36..67  amount (uint256)
    Returns ``("", 0)`` for anything that doesn't look like a transfer.
    """
    if not data:
        return "", 0
    s = data.lower()
    if s.startswith("0x"):
        s = s[2:]
    if not s.startswith("a9059cbb") or len(s) < 8 + 64 * 2:
        return "", 0
    addr_hex = "41" + s[8 + 24 : 8 + 64]  # last 20 bytes of the 32-byte slot, prefix 0x41 for Tron
    amount_hex = s[8 + 64 : 8 + 128]
    try:
        amount = int(amount_hex, 16)
    except ValueError:
        amount = 0
    return _hex_to_base58(addr_hex), amount
