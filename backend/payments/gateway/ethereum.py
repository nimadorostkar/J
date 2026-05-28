# === FILE: backend/payments/gateway/ethereum.py ===
"""Ethereum (ERC20-USDT) gateway client.

Read paths use Etherscan's free Logs API for cheap tx-listing — no
web3.py / JSON-RPC archive node required for the scanner. Write paths
use web3.py when installed; otherwise we raise so ops notices.
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
    from web3 import Web3  # type: ignore
    from web3.middleware import geth_poa_middleware  # type: ignore
    from eth_account import Account  # type: ignore

    _HAS_WEB3 = True
except Exception:  # pragma: no cover
    _HAS_WEB3 = False


# ABI for the bare minimum we need (transfer + balanceOf).
_ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]

# keccak256("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class EthereumGateway(BaseGatewayClient):
    NETWORK = "ERC20"

    @property
    def DECIMALS(self) -> int:  # type: ignore[override]
        return int(getattr(settings, "USDT_DECIMALS_ERC20", 6))

    @property
    def _rpc(self) -> str:
        return getattr(settings, "ETHEREUM_RPC_URL", "")

    @property
    def _etherscan(self) -> str:
        return getattr(settings, "ETHERSCAN_API_URL", "https://api.etherscan.io/api")

    @property
    def _contract(self) -> str:
        return getattr(settings, "USDT_ERC20_CONTRACT", "").lower()

    @property
    def _master_address(self) -> str:
        return getattr(settings, "USDT_ERC20_WALLET", "")

    # ── HTTP helpers ─────────────────────────────────────────────────
    def _etherscan_get(self, params: dict) -> dict:
        key = getattr(settings, "ETHEREUM_API_KEY", "")
        if key:
            params = {**params, "apikey": key}
        try:
            r = requests.get(self._etherscan, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise GatewayError(f"Etherscan failure: {e}", retryable=True) from e
        if not r.ok:
            raise GatewayError(
                f"Etherscan {r.status_code}: {r.text[:300]}",
                retryable=r.status_code in (429, 408, 503),
            )
        body = r.json() or {}
        if body.get("status") == "0" and body.get("message") not in {"No transactions found", "OK"}:
            # Etherscan returns "0" for "no records" too — only raise on real errors.
            raise GatewayError(f"Etherscan API error: {body.get('result')}", retryable=True)
        return body

    def _rpc_call(self, method: str, params: list) -> dict:
        if not self._rpc:
            raise GatewayError("ETHEREUM_RPC_URL not configured", retryable=False)
        try:
            r = requests.post(
                self._rpc,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise GatewayError(f"Ethereum RPC failure: {e}", retryable=True) from e
        if not r.ok:
            raise GatewayError(f"Ethereum RPC {r.status_code}", retryable=True)
        body = r.json() or {}
        if "error" in body:
            raise GatewayError(f"Ethereum RPC error: {body['error']}", retryable=True)
        return body

    # ── BaseGatewayClient implementation ─────────────────────────────
    def get_chain_height(self) -> int:
        body = self._rpc_call("eth_blockNumber", [])
        result = body.get("result", "0x0")
        return int(result, 16) if isinstance(result, str) else int(result or 0)

    def get_transfer(self, tx_hash: str) -> Optional[ChainTransfer]:
        if not tx_hash:
            return None
        if self.dry_run and tx_hash.startswith(("simulated-", "manual-")):
            return ChainTransfer(
                tx_hash=tx_hash,
                log_index=0,
                block_number=0,
                from_address="",
                to_address=self._master_address,
                amount_usdt=Decimal("0"),
                confirmations=getattr(settings, "MIN_CONFIRMATIONS_ERC20", 12) + 1,
                network=self.NETWORK,
            )

        body = self._rpc_call("eth_getTransactionReceipt", [tx_hash])
        receipt = body.get("result")
        if not receipt:
            return None

        block_number = int(receipt.get("blockNumber", "0x0"), 16)
        height = self.get_chain_height()
        confs = max(0, height - block_number) if block_number else 0

        # Find the USDT Transfer log and pull recipient + amount.
        for log_index, log in enumerate(receipt.get("logs") or []):
            if (log.get("address") or "").lower() != self._contract:
                continue
            topics = log.get("topics") or []
            if not topics or topics[0].lower() != TRANSFER_TOPIC:
                continue
            from_addr = "0x" + topics[1][-40:] if len(topics) > 1 else ""
            to_addr = "0x" + topics[2][-40:] if len(topics) > 2 else ""
            data = (log.get("data") or "0x0").replace("0x", "")
            amount_raw = int(data or "0", 16)
            return ChainTransfer(
                tx_hash=tx_hash,
                log_index=log_index,
                block_number=block_number,
                from_address=from_addr,
                to_address=to_addr,
                amount_usdt=self._from_token_units(amount_raw),
                confirmations=confs,
                network=self.NETWORK,
            )
        return None

    def list_incoming_transfers(
        self, *, address: str, from_block: int = 0, limit: int = 50
    ) -> Iterable[ChainTransfer]:
        if not address or not self._contract:
            return []
        params = {
            "module": "account",
            "action": "tokentx",
            "contractaddress": self._contract,
            "address": address,
            "startblock": max(from_block, 0),
            "endblock": 99999999,
            "page": 1,
            "offset": min(limit, 100),
            "sort": "asc",
        }
        body = self._etherscan_get(params)
        results = []
        height = self.get_chain_height() if self._rpc else 0
        for row in body.get("result") or []:
            # Skip outbound transfers.
            if (row.get("to") or "").lower() != address.lower():
                continue
            block_number = int(row.get("blockNumber") or 0)
            confs = max(0, height - block_number) if height and block_number else 0
            amount_raw = int(row.get("value") or 0)
            results.append(
                ChainTransfer(
                    tx_hash=row.get("hash") or "",
                    log_index=int(row.get("transactionIndex") or 0),
                    block_number=block_number,
                    from_address=row.get("from") or "",
                    to_address=row.get("to") or "",
                    amount_usdt=self._from_token_units(amount_raw),
                    confirmations=confs,
                    network=self.NETWORK,
                )
            )
        return results

    def send_usdt(self, *, to_address: str, amount_usdt: Decimal) -> str:
        if self.dry_run:
            simulated = f"simulated-erc20-{abs(hash((to_address, str(amount_usdt))))%(16**16):016x}"
            logger.info(
                "EthereumGateway dry-run: would send %s USDT to %s — tx=%s",
                amount_usdt, to_address, simulated,
            )
            return simulated

        if not _HAS_WEB3:
            raise GatewayError(
                "web3.py is required for outbound Ethereum transfers. Install with `pip install web3`.",
                retryable=False,
            )

        pk = getattr(settings, "ETHEREUM_HOT_WALLET_PRIVATE_KEY", "")
        if not pk:
            raise GatewayError("ETHEREUM_HOT_WALLET_PRIVATE_KEY not configured", retryable=False)
        if not self._contract or not self._master_address:
            raise GatewayError("Ethereum contract/master wallet not configured", retryable=False)

        try:
            w3 = Web3(Web3.HTTPProvider(self._rpc, request_kwargs={"timeout": self.timeout}))
            # POA networks (Goerli/Sepolia) need PoA middleware.
            try:
                w3.middleware_onion.inject(geth_poa_middleware, layer=0)
            except Exception:
                pass

            account = Account.from_key(pk if pk.startswith("0x") else "0x" + pk)
            if account.address.lower() != self._master_address.lower():
                raise GatewayError(
                    "ETHEREUM_HOT_WALLET_PRIVATE_KEY does not match USDT_ERC20_WALLET — refusing to broadcast.",
                    retryable=False,
                )

            contract = w3.eth.contract(
                address=Web3.to_checksum_address(self._contract),
                abi=_ERC20_ABI,
            )
            raw_amount = self._to_token_units(amount_usdt)
            nonce = w3.eth.get_transaction_count(account.address)
            tx = contract.functions.transfer(
                Web3.to_checksum_address(to_address), raw_amount
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "chainId": w3.eth.chain_id,
                "gas": 80_000,
                "maxFeePerGas": w3.eth.gas_price * 2,
                "maxPriorityFeePerGas": w3.to_wei("1.5", "gwei"),
            })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction).hex()
            return tx_hash
        except GatewayError:
            raise
        except Exception as e:
            msg = str(e).lower()
            if "insufficient" in msg or "gas" in msg or "funds" in msg:
                raise InsufficientGas(str(e)) from e
            raise GatewayError(f"Ethereum broadcast failed: {e}", retryable=True) from e
