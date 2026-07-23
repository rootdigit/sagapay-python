"""Models for the SagaPay SDK."""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, ConfigDict, Field


class NetworkType(str, Enum):
    """Supported blockchain network types."""
    
    ERC20 = "ERC20"
    BEP20 = "BEP20"
    TRC20 = "TRC20"
    POLYGON = "POLYGON"
    SOLANA = "SOLANA"


class TransactionType(str, Enum):
    """Transaction types."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


class IpnType(str, Enum):
    """IPN notification types (the server sends uppercase values)."""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"


class TransactionStatus(str, Enum):
    """Transaction statuses."""
    
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AddressType(str, Enum):
    """Address types."""
    
    TEMPORARY = "TEMPORARY"
    PERMANENT = "PERMANENT"


class CreateDepositParams(BaseModel):
    """Parameters for creating a deposit."""

    model_config = ConfigDict(populate_by_name=True)

    network_type: NetworkType = Field(alias="networkType")
    contract_address: str = Field(alias="contractAddress")
    amount: str
    ipn_url: str = Field(alias="ipnUrl")
    udf: Optional[str] = None
    type: Optional[AddressType] = None
    transfer_balance: Optional[bool] = Field(default=None, alias="transferBalance")

    def dict(self, *args, **kwargs):
        """Serialize to the camelCase field names the API expects.

        Unset optionals must be omitted rather than sent as null: the API
        applies its own defaults (type=TEMPORARY, transferBalance=true) only
        when a field is absent.
        """
        kwargs.setdefault("by_alias", True)
        return self.model_dump(*args, **kwargs)


class CreateWithdrawalParams(BaseModel):
    """Parameters for creating a withdrawal."""

    model_config = ConfigDict(populate_by_name=True)

    network_type: NetworkType = Field(alias="networkType")
    contract_address: str = Field(alias="contractAddress")
    address: str
    amount: str
    ipn_url: str = Field(alias="ipnUrl")
    udf: Optional[str] = None

    def dict(self, *args, **kwargs):
        """Serialize to the camelCase field names the API expects."""
        kwargs.setdefault("by_alias", True)
        return self.model_dump(*args, **kwargs)


class DepositResponse(BaseModel):
    """Response from creating a deposit."""

    id: str
    address: str
    expires_at: Optional[datetime] = Field(default=None, alias="expiresAt")
    amount: str
    status: TransactionStatus


class WithdrawalResponse(BaseModel):
    """Response from creating a withdrawal."""
    
    id: str
    status: TransactionStatus
    fee: str


class Token(BaseModel):
    """Token information.

    Note: network_type and contract_address are only present in some
    responses (e.g. check-transaction-status); fetch-wallet-balance
    returns tokens without them.
    """

    network_type: Optional[NetworkType] = Field(default=None, alias="networkType")
    contract_address: Optional[str] = Field(default=None, alias="contractAddress")
    symbol: str
    name: str
    decimals: int


class Balance(BaseModel):
    """Balance information."""
    
    raw: str
    formatted: str


class Transaction(BaseModel):
    """Transaction details."""

    id: str
    transaction_type: TransactionType = Field(alias="transactionType")
    status: TransactionStatus
    amount: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    tx_hash: Optional[str] = Field(default=None, alias="txHash")
    network_type: NetworkType = Field(alias="networkType")
    contract_address: str = Field(alias="contractAddress")
    address: str
    udf: Optional[str] = None
    token: Token
    confirmations: Optional[int] = None
    fee: Optional[str] = None
    processed_at: Optional[datetime] = Field(default=None, alias="processedAt")


class TransactionStatusResponse(BaseModel):
    """Response from checking transaction status."""

    address: Optional[str] = None
    transaction_type: TransactionType = Field(alias="transactionType")
    count: int
    transactions: List[Transaction]


class WalletBalanceResponse(BaseModel):
    """Response from fetching wallet balance."""
    
    address: str
    network_type: NetworkType = Field(alias="networkType")
    contract_address: str = Field(alias="contractAddress")
    token: Token
    balance: Balance


class WebhookPayload(BaseModel):
    """Webhook payload sent in notifications."""

    id: str
    type: IpnType
    status: TransactionStatus
    address: str
    network_type: NetworkType = Field(alias="networkType")
    amount: str
    udf: Optional[str] = None
    tx_hash: Optional[str] = Field(default=None, alias="txHash")
    timestamp: datetime


class VerifyIpnResponse(BaseModel):
    """Response from verifying an IPN notification."""

    verified: bool