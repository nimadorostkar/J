# === FILE: backend/payments/tests/test_gateway_clients.py ===
"""Unit tests for the chain-specific gateway clients.

We mock HTTP at the `requests` layer so these tests don't hit
TronGrid / Etherscan / Infura.
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings

from payments.gateway import get_client
from payments.gateway.base import ChainTransfer
from payments.gateway.tron import _decode_trc20_transfer, _hex_to_base58


class GatewayFactoryTests(TestCase):
    def test_factory_returns_tron(self):
        c = get_client("TRC20")
        self.assertEqual(c.NETWORK, "TRC20")

    def test_factory_returns_ethereum(self):
        c = get_client("ERC20")
        self.assertEqual(c.NETWORK, "ERC20")

    def test_factory_rejects_unknown(self):
        with self.assertRaises(ValueError):
            get_client("BTC")


class TronABIDecodingTests(TestCase):
    def test_decode_transfer_returns_address_and_amount(self):
        # transfer(address,uint256) → recipient + 5_000_000 (= 5 USDT @ 6 dp)
        # Recipient address (hex Tron, no 0x41 prefix): 20 bytes of "11"...
        recipient_hex = "11" * 20
        # amount = 5 * 10^6 = 0x4c4b40 → left-pad to 32 bytes
        data = (
            "0xa9059cbb"
            + "0" * 24 + recipient_hex
            + "0" * (64 - 6) + "4c4b40"
        )
        addr, amount = _decode_trc20_transfer(data)
        # Convert the expected hex address to base58 (with 0x41 prefix).
        expected = _hex_to_base58("41" + recipient_hex)
        self.assertEqual(addr, expected)
        self.assertEqual(amount, 5_000_000)

    def test_decode_transfer_returns_empty_on_nonsense(self):
        self.assertEqual(_decode_trc20_transfer(""), ("", 0))
        self.assertEqual(_decode_trc20_transfer("0xdeadbeef"), ("", 0))


@override_settings(
    GATEWAY_DRY_RUN=True,
    MIN_CONFIRMATIONS_TRC20=2,
    MIN_CONFIRMATIONS_ERC20=2,
)
class DryRunTransferLookup(TestCase):
    def test_tron_dry_run_returns_confirmed(self):
        c = get_client("TRC20")
        t = c.get_transfer("simulated-abc")
        self.assertIsNotNone(t)
        self.assertGreater(t.confirmations, 0)

    def test_ethereum_dry_run_returns_confirmed(self):
        c = get_client("ERC20")
        t = c.get_transfer("simulated-xyz")
        self.assertIsNotNone(t)
        self.assertGreater(t.confirmations, 0)


@override_settings(
    GATEWAY_DRY_RUN=True,
    USDT_TRC20_WALLET="TMasterAddr",
)
class TronListIncomingTests(TestCase):
    def test_list_calls_trongrid(self):
        c = get_client("TRC20")
        fake = {
            "data": [
                {
                    "transaction_id": "0xdeadbeef",
                    "block_timestamp": 1700000000_000,
                    "from": "TAlice",
                    "to": "TMasterAddr",
                    "value": "1000000",  # 1 USDT @ 6dp
                }
            ]
        }
        with patch.object(c, "_get", return_value=fake), \
             patch.object(c, "get_chain_height", return_value=999999):
            transfers = list(c.list_incoming_transfers(address="TMasterAddr"))
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0].amount_usdt, Decimal("1.00000000"))
        self.assertEqual(transfers[0].from_address, "TAlice")


class EthereumDryRunSendTests(TestCase):
    @override_settings(GATEWAY_DRY_RUN=True)
    def test_send_returns_simulated_hash(self):
        c = get_client("ERC20")
        h = c.send_usdt(to_address="0x1234567890abcdef1234567890abcdef12345678", amount_usdt=Decimal("1.5"))
        self.assertTrue(h.startswith("simulated-erc20-"))

    @override_settings(GATEWAY_DRY_RUN=True)
    def test_tron_send_returns_simulated_hash(self):
        c = get_client("TRC20")
        h = c.send_usdt(to_address="TXYZ", amount_usdt=Decimal("2.5"))
        self.assertTrue(h.startswith("simulated-trc20-"))
