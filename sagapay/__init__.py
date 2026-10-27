"""
SagaPay Python SDK

This module provides a Python interface to the SagaPay blockchain payment gateway API.
SagaPay is the world's first free, non-custodial blockchain payment gateway service provider.
"""

from .client import Client
from .models import (
    NetworkType,
    TransactionType,
    TransactionStatus,
    AddressType,
    IpnType,
    CreateDepositParams,
    CreateWithdrawalParams,
    DepositResponse,
    WithdrawalResponse,
    TransactionStatusResponse,
    VerifyIpnResponse,
    WalletBalanceResponse,
    WebhookPayload,
)
from .exceptions import (
    SagaPayError,
    APIError,
    ValidationError,
    NetworkError,
    WebhookError,
)
from .webhook import (
    DEFAULT_MAX_AGE_SECONDS,
    SIGNATURE_HEADER,
    WebhookHandler,
    is_ipn_fresh,
    parse_payload,
)

__version__ = "0.5.0"
__all__ = [
    "Client",
    "NetworkType",
    "TransactionType",
    "TransactionStatus",
    "AddressType",
    "IpnType",
    "CreateDepositParams",
    "CreateWithdrawalParams",
    "DepositResponse",
    "WithdrawalResponse",
    "TransactionStatusResponse",
    "VerifyIpnResponse",
    "WalletBalanceResponse",
    "WebhookPayload",
    "SagaPayError",
    "APIError",
    "ValidationError",
    "NetworkError",
    "WebhookError",
    "WebhookHandler",
    "SIGNATURE_HEADER",
    "DEFAULT_MAX_AGE_SECONDS",
    "is_ipn_fresh",
    "parse_payload",
]
