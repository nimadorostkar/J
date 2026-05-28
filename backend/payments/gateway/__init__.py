# === FILE: backend/payments/gateway/__init__.py ===
"""Gateway client factory.

Usage::

    from payments.gateway import get_client
    client = get_client("TRC20")
    confs = client.get_confirmations(tx_hash)
"""
from django.conf import settings

from .base import BaseGatewayClient, ChainTransfer, GatewayError
from .ethereum import EthereumGateway
from .tron import TronGateway

__all__ = [
    "BaseGatewayClient",
    "ChainTransfer",
    "GatewayError",
    "EthereumGateway",
    "TronGateway",
    "get_client",
]


_REGISTRY = {
    "TRC20": TronGateway,
    "ERC20": EthereumGateway,
}


def get_client(network: str) -> BaseGatewayClient:
    """Return a configured gateway client for the given network.

    Raises `ValueError` for unknown networks. The returned object is
    cheap to construct (just stores config) so callers don't need to
    cache it.
    """
    network = (network or "").upper()
    cls = _REGISTRY.get(network)
    if cls is None:
        raise ValueError(f"Unsupported network: {network!r}")
    return cls(
        dry_run=bool(getattr(settings, "GATEWAY_DRY_RUN", True)),
        timeout=int(getattr(settings, "GATEWAY_RPC_TIMEOUT_SECONDS", 15)),
    )
