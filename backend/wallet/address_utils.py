# === FILE: backend/wallet/address_utils.py ===
"""Network-specific wallet address validators."""
import base58
from eth_utils import is_checksum_address, to_checksum_address


def validate_trc20_address(addr: str) -> bool:
    """TRON addresses are base58 starting with 'T' and decode to 21 bytes
    (0x41 prefix + 20-byte hash + 4-byte checksum after decode-check)."""
    if not addr or not isinstance(addr, str):
        return False
    if not addr.startswith("T") or not (33 <= len(addr) <= 35):
        return False
    try:
        decoded = base58.b58decode_check(addr)
        return len(decoded) == 21 and decoded[0] == 0x41
    except Exception:
        return False


def validate_erc20_address(addr: str) -> bool:
    """ERC20 addresses are 20-byte hex starting with '0x'. We accept checksummed
    or all-lower/all-upper case."""
    if not addr or not isinstance(addr, str):
        return False
    if not addr.startswith("0x") or len(addr) != 42:
        return False
    body = addr[2:]
    try:
        int(body, 16)
    except ValueError:
        return False
    # If mixed case, must be a valid EIP-55 checksum
    if body != body.lower() and body != body.upper():
        try:
            return is_checksum_address(addr)
        except Exception:
            return False
    return True


def validate_address(network: str, addr: str) -> bool:
    if network == "TRC20":
        return validate_trc20_address(addr)
    if network == "ERC20":
        return validate_erc20_address(addr)
    return False
