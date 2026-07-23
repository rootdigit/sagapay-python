"""Tests for webhook signature verification and payload processing."""

import hashlib
import hmac
import json
import unittest

from sagapay import IpnType, TransactionStatus, WebhookError, WebhookHandler


IPN_SECRET = "platform-issued-ipn-secret"

PAYLOAD = {
    "id": "8f2c1b6e-3d5a-4c7b-9e1f-2a3b4c5d6e7f",
    "type": "DEPOSIT",
    "status": "COMPLETED",
    "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "networkType": "BEP20",
    "amount": "100.5",
    "udf": "order-123",
    "txHash": "0xabc123",
    "timestamp": "2026-07-24T00:00:00.000Z",
}


def raw_body(payload=None):
    """Serialize a payload the way the server sends it."""
    return json.dumps(payload if payload is not None else PAYLOAD)


def sign(body, secret=IPN_SECRET):
    """Produce the hex digest the server puts in X-Sagapay-Signature."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class VerifySignatureTest(unittest.TestCase):
    def setUp(self):
        self.handler = WebhookHandler(ipn_secret=IPN_SECRET)
        self.body = raw_body()

    def test_accepts_sha256_prefixed_signature(self):
        header = "sha256=" + sign(self.body)
        self.assertTrue(self.handler.verify_signature(self.body, header))

    def test_accepts_bare_hex_signature(self):
        self.assertTrue(self.handler.verify_signature(self.body, sign(self.body)))

    def test_accepts_bytes_body(self):
        body = self.body.encode("utf-8")
        self.assertTrue(self.handler.verify_signature(body, "sha256=" + sign(body)))

    def test_rejects_tampered_body(self):
        tampered = raw_body({**PAYLOAD, "amount": "999999.0"})
        self.assertFalse(self.handler.verify_signature(tampered, "sha256=" + sign(self.body)))

    def test_rejects_signature_from_wrong_secret(self):
        header = "sha256=" + sign(self.body, secret="not-the-ipn-secret")
        self.assertFalse(self.handler.verify_signature(self.body, header))

    def test_missing_signature_raises(self):
        with self.assertRaises(WebhookError):
            self.handler.verify_signature(self.body, None)

    def test_no_secret_configured_raises(self):
        with self.assertRaises(WebhookError):
            WebhookHandler().verify_signature(self.body, "sha256=" + sign(self.body))


class ProcessWebhookTest(unittest.TestCase):
    def test_verifies_and_parses_with_secret(self):
        handler = WebhookHandler(ipn_secret=IPN_SECRET)
        body = raw_body()
        result = handler.process_webhook(body, "sha256=" + sign(body))

        self.assertEqual(result.id, PAYLOAD["id"])
        self.assertEqual(result.type, IpnType.DEPOSIT)
        self.assertEqual(result.status, TransactionStatus.COMPLETED)
        self.assertEqual(result.amount, "100.5")
        self.assertEqual(result.tx_hash, "0xabc123")
        self.assertEqual(result.udf, "order-123")

    def test_bad_signature_raises(self):
        handler = WebhookHandler(ipn_secret=IPN_SECRET)
        with self.assertRaises(WebhookError):
            handler.process_webhook(raw_body(), "sha256=" + "0" * 64)

    def test_skips_verification_without_secret(self):
        handler = WebhookHandler()
        result = handler.process_webhook(raw_body())
        self.assertEqual(result.type, IpnType.DEPOSIT)

    def test_dict_payload_rejected_when_secret_configured(self):
        handler = WebhookHandler(ipn_secret=IPN_SECRET)
        with self.assertRaises(WebhookError):
            handler.process_webhook(PAYLOAD, "sha256=" + sign(raw_body()))

    def test_invalid_json_raises(self):
        with self.assertRaises(WebhookError):
            WebhookHandler().process_webhook("not json at all")

    def test_withdrawal_payload_parses(self):
        handler = WebhookHandler()
        result = handler.process_webhook(
            raw_body({**PAYLOAD, "type": "WITHDRAWAL", "udf": None, "txHash": None})
        )
        self.assertEqual(result.type, IpnType.WITHDRAWAL)
        self.assertIsNone(result.udf)
        self.assertIsNone(result.tx_hash)


if __name__ == "__main__":
    unittest.main()
