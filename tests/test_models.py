"""Tests that the response models parse real server payload shapes."""

import unittest

from sagapay import (
    CreateDepositParams,
    CreateWithdrawalParams,
    NetworkType,
    TransactionStatus,
    TransactionStatusResponse,
    TransactionType,
    VerifyIpnResponse,
    WalletBalanceResponse,
)
from sagapay.models import DepositResponse, WithdrawalResponse


class WalletBalanceResponseTest(unittest.TestCase):
    """fetch-wallet-balance returns a token WITHOUT networkType/contractAddress."""

    PAYLOAD = {
        "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
        "networkType": "BEP20",
        "contractAddress": "0x55d398326f99059ff775485246999027b3197955",
        "token": {"symbol": "USDT", "name": "Tether USD", "decimals": 18},
        "balance": {"raw": "1000000000000000000", "formatted": "1"},
    }

    def test_parses_token_without_network_fields(self):
        result = WalletBalanceResponse.model_validate(self.PAYLOAD)

        self.assertEqual(result.network_type, NetworkType.BEP20)
        self.assertEqual(result.token.symbol, "USDT")
        self.assertEqual(result.token.decimals, 18)
        self.assertIsNone(result.token.network_type)
        self.assertIsNone(result.token.contract_address)
        self.assertEqual(result.balance.raw, "1000000000000000000")
        self.assertEqual(result.balance.formatted, "1")

    def test_parses_native_coin_balance(self):
        payload = {
            **self.PAYLOAD,
            "contractAddress": "0",
            "token": {"symbol": "TRC20", "name": "TRC20", "decimals": 6},
        }
        result = WalletBalanceResponse.model_validate({**payload, "networkType": "TRC20"})
        self.assertEqual(result.contract_address, "0")
        self.assertEqual(result.token.decimals, 6)


class TransactionStatusResponseTest(unittest.TestCase):
    """check-transaction-status returns a fully-populated token plus per-type fields."""

    def test_parses_deposit_with_confirmations(self):
        payload = {
            "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "transactionType": "deposit",
            "count": 1,
            "transactions": [
                {
                    "id": "8f2c1b6e-3d5a-4c7b-9e1f-2a3b4c5d6e7f",
                    "transactionType": "deposit",
                    "status": "COMPLETED",
                    "amount": "100.5",
                    "createdAt": "2026-07-24T00:00:00.000Z",
                    "updatedAt": "2026-07-24T00:05:00.000Z",
                    "txHash": "0xabc123",
                    "confirmations": 12,
                    "networkType": "BEP20",
                    "contractAddress": "0x55d398326f99059ff775485246999027b3197955",
                    "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
                    "udf": "order-123",
                    "token": {
                        "networkType": "BEP20",
                        "contractAddress": "0x55d398326f99059ff775485246999027b3197955",
                        "symbol": "USDT",
                        "name": "Tether USD",
                        "decimals": 18,
                    },
                }
            ],
        }

        result = TransactionStatusResponse.model_validate(payload)
        tx = result.transactions[0]

        self.assertEqual(result.count, 1)
        self.assertEqual(result.transaction_type, TransactionType.DEPOSIT)
        self.assertEqual(tx.status, TransactionStatus.COMPLETED)
        self.assertEqual(tx.confirmations, 12)
        self.assertEqual(tx.token.network_type, NetworkType.BEP20)
        self.assertEqual(tx.token.symbol, "USDT")
        # Deposit items carry no fee/processedAt.
        self.assertIsNone(tx.fee)
        self.assertIsNone(tx.processed_at)

    def test_parses_withdrawal_with_fee_and_processed_at(self):
        payload = {
            "address": "0xdest",
            "transactionType": "withdrawal",
            "count": 1,
            "transactions": [
                {
                    "id": "1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d",
                    "transactionType": "withdrawal",
                    "status": "COMPLETED",
                    "amount": "50.75",
                    "fee": "0.5",
                    "processedAt": "2026-07-24T00:10:00.000Z",
                    "createdAt": "2026-07-24T00:00:00.000Z",
                    "updatedAt": "2026-07-24T00:10:00.000Z",
                    "txHash": None,
                    "networkType": "POLYGON",
                    "contractAddress": "0",
                    "address": "0xdest",
                    "udf": None,
                    "token": {
                        "networkType": "POLYGON",
                        "contractAddress": "0",
                        "symbol": "POL",
                        "name": "Polygon",
                        "decimals": 18,
                    },
                }
            ],
        }

        tx = TransactionStatusResponse.model_validate(payload).transactions[0]

        self.assertEqual(tx.fee, "0.5")
        self.assertIsNotNone(tx.processed_at)
        self.assertIsNone(tx.tx_hash)
        self.assertIsNone(tx.udf)
        self.assertIsNone(tx.confirmations)


class CreateResponseTest(unittest.TestCase):
    def test_deposit_response_temporary(self):
        result = DepositResponse.model_validate(
            {
                "id": "dep-1",
                "address": "0xabc",
                "expiresAt": "2026-07-25T00:00:00.000Z",
                "amount": "100.5",
                "status": "PENDING",
            }
        )
        self.assertIsNotNone(result.expires_at)
        self.assertEqual(result.status, TransactionStatus.PENDING)

    def test_deposit_response_permanent_has_null_expiry(self):
        result = DepositResponse.model_validate(
            {
                "id": "dep-2",
                "address": "0xabc",
                "expiresAt": None,
                "amount": "100.5",
                "status": "PENDING",
            }
        )
        self.assertIsNone(result.expires_at)

    def test_withdrawal_response(self):
        result = WithdrawalResponse.model_validate(
            {"id": "wd-1", "status": "PENDING", "fee": "0.5"}
        )
        self.assertEqual(result.fee, "0.5")

    def test_verify_ipn_response(self):
        self.assertTrue(VerifyIpnResponse.model_validate({"verified": True}).verified)
        self.assertFalse(VerifyIpnResponse.model_validate({"verified": False}).verified)


class CreateDepositParamsTest(unittest.TestCase):
    """The client serializes bodies with dict(exclude_none=True)."""

    def test_serializes_camel_case_wire_names(self):
        params = CreateDepositParams(
            network_type=NetworkType.BEP20,
            contract_address="0x55d398326f99059ff775485246999027b3197955",
            amount="100.50",
            ipn_url="https://example.com/ipn",
            udf="order-123",
            transfer_balance=False,
        )
        body = params.dict(exclude_none=True)

        self.assertEqual(body["networkType"], "BEP20")
        self.assertEqual(body["contractAddress"], "0x55d398326f99059ff775485246999027b3197955")
        self.assertEqual(body["ipnUrl"], "https://example.com/ipn")
        # False must survive exclude_none — it is how a merchant opts out of sweeping.
        self.assertEqual(body["transferBalance"], False)
        # amount must stay a string — the server validates ^[0-9]+\.?[0-9]*$
        self.assertIsInstance(body["amount"], str)
        self.assertNotIn("transfer_balance", body)
        self.assertNotIn("network_type", body)

    def test_omits_unset_optionals(self):
        """Unset optionals must be absent, not null: the server coerces an
        explicit null to false/"" instead of applying its own defaults."""
        params = CreateDepositParams(
            network_type=NetworkType.ERC20,
            contract_address="0",
            amount="1",
            ipn_url="https://example.com/ipn",
        )
        body = params.dict(exclude_none=True)

        self.assertNotIn("transferBalance", body)
        self.assertNotIn("type", body)
        self.assertNotIn("udf", body)

    def test_withdrawal_params_serialize_camel_case(self):
        body = CreateWithdrawalParams(
            network_type=NetworkType.POLYGON,
            contract_address="0",
            address="0xdest",
            amount="50.75",
            ipn_url="https://example.com/ipn",
        ).dict(exclude_none=True)

        self.assertEqual(body["networkType"], "POLYGON")
        self.assertEqual(body["contractAddress"], "0")
        self.assertEqual(body["ipnUrl"], "https://example.com/ipn")
        self.assertEqual(body["address"], "0xdest")
        self.assertNotIn("udf", body)


if __name__ == "__main__":
    unittest.main()
