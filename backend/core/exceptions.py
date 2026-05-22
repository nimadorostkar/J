# === FILE: backend/core/exceptions.py ===
"""Centralised DRF exception handler."""
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("tokenvault")


class WithdrawalLocked(Exception):
    """Raised when a user attempts a withdrawal without meeting both gates."""

    def __init__(self, missing_conditions, details):
        self.missing_conditions = missing_conditions
        self.details = details
        super().__init__("Withdrawal locked.")


class InsufficientBalance(Exception):
    pass


def api_exception_handler(exc, context):
    if isinstance(exc, WithdrawalLocked):
        return Response(
            {
                "code": "WITHDRAWAL_LOCKED",
                "message": "Withdrawal requires completing both conditions.",
                "missingConditions": exc.missing_conditions,
                "details": exc.details,
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    if isinstance(exc, InsufficientBalance):
        return Response(
            {"code": "INSUFFICIENT_BALANCE", "message": str(exc) or "Insufficient balance."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled exception")
        return Response(
            {"code": "SERVER_ERROR", "message": "Internal server error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return response
