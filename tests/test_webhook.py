"""Tests for webhook signature verification and payload processing."""

import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone

from sagapay import (
    SIGNATURE_HEADER,
    IpnType,
    TransactionStatus,
    WebhookError,
    WebhookHandler,
    is_ipn_fresh,
    parse_payload,
)


# A merchant signing secret is a 64-character hex string, used as the HMAC key
# exactly as written.
IPN_SECRET = "a3f1c2e4b5d697881234567890abcdef00112233445566778899aabbccddeeff"

PAYLOAD = {
    "id": "8f2c1b6e-3d5a-4c7b-9e1f-2a3b4c5d6e7f",
    "type": "DEPOSIT",
    "status": "COMPLETED",
    "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "networkType": "BEP20",
    "asset": "USDT",
    "contractAddress": "0x55d398326f99059fF775485246999027B3197955",
    "amount": "100.5",
    "udf": "order-123",
    "txHash": "0xabc123",
    "timestamp": "2026-07-24T00:00:00.000Z",
}


def raw_body(payload=None):
    """Serialize a payload the way the server sends it."""
    return json.dumps(payload if payload is not None else PAYLOAD)


def sign(body, secret=IPN_SECRET):
    """Produce the hex digest the server puts in X-Sagapay-Merchant-Signature."""
    if isinstance(body, str):
        body = body.encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class VerifySignatureTest(unittest.TestCase):
    def setUp(self):
        self.handler = WebhookHandler(IPN_SECRET)
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

    def test_accepts_upper_case_hex(self):
        header = "sha256=" + sign(self.body).upper()
        self.assertTrue(self.handler.verify_signature(self.body, header))

    def test_rejects_malformed_signatures(self):
        digest = sign(self.body)
        for bad in (digest[:62], digest + "00", "zz" + digest[2:], "sha256=", "sha256= "):
            with self.subTest(bad=bad):
                self.assertFalse(self.handler.verify_signature(self.body, bad))

    def test_signing_secret_is_required(self):
        with self.assertRaises(ValueError):
            WebhookHandler("")
        with self.assertRaises(TypeError):
            WebhookHandler()

    def test_signature_header_name(self):
        self.assertEqual(SIGNATURE_HEADER, "X-Sagapay-Merchant-Signature")

    def test_matches_the_sagapay_signer(self):
        # Produced by the SagaPay signer (core-api utils/ipnSignature.js) for
        # a test merchant; keeps this SDK in step with what the platform sends.
        secret = "f59949bf79a73e05a41f10d2333a41b80644430f5220f468171392df355663a7"
        body = (
            '{"id":"dep-1","type":"DEPOSIT","status":"COMPLETED","address":"0xabc",'
            '"networkType":"BEP20","asset":"USDT",'
            '"contractAddress":"0x55d398326f99059fF775485246999027B3197955",'
            '"amount":"100.5","udf":null,"txHash":"0xdef","timestamp":"2026-10-27T00:00:00.000Z"}'
        )
        header = "sha256=a9841956a4b8ccf048f953081db6892e69da181b5792dfcf8604ea4795f6a469"
        handler = WebhookHandler(secret)
        self.assertTrue(handler.verify_signature(body, header))
        self.assertFalse(handler.verify_signature(body.replace("100.5", "100.6"), header))


class ProcessWebhookTest(unittest.TestCase):
    def test_verifies_and_parses_with_secret(self):
        handler = WebhookHandler(IPN_SECRET)
        body = raw_body()
        result = handler.process_webhook(body, "sha256=" + sign(body))

        self.assertEqual(result.id, PAYLOAD["id"])
        self.assertEqual(result.type, IpnType.DEPOSIT)
        self.assertEqual(result.status, TransactionStatus.COMPLETED)
        self.assertEqual(result.amount, "100.5")
        self.assertEqual(result.tx_hash, "0xabc123")
        self.assertEqual(result.udf, "order-123")
        self.assertEqual(result.asset, "USDT")
        self.assertEqual(result.contract_address, PAYLOAD["contractAddress"])

    def test_bad_signature_raises(self):
        handler = WebhookHandler(IPN_SECRET)
        with self.assertRaises(WebhookError):
            handler.process_webhook(raw_body(), "sha256=" + "0" * 64)

    def test_missing_signature_raises(self):
        handler = WebhookHandler(IPN_SECRET)
        with self.assertRaises(WebhookError):
            handler.process_webhook(raw_body(), None)

    def test_dict_payload_rejected(self):
        handler = WebhookHandler(IPN_SECRET)
        with self.assertRaises(WebhookError):
            handler.process_webhook(PAYLOAD, "sha256=" + sign(raw_body()))

    def test_invalid_json_raises(self):
        body = "not json at all"
        with self.assertRaises(WebhookError):
            WebhookHandler(IPN_SECRET).process_webhook(body, sign(body))

    def test_stale_webhook_rejected_when_max_age_set(self):
        handler = WebhookHandler(IPN_SECRET, max_age_seconds=3600)
        body = raw_body()  # timestamp is in 2026-07, long past
        with self.assertRaises(WebhookError):
            handler.process_webhook(body, sign(body))

    def test_fresh_webhook_accepted_when_max_age_set(self):
        handler = WebhookHandler(IPN_SECRET, max_age_seconds=3600)
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        body = raw_body({**PAYLOAD, "timestamp": now})
        self.assertEqual(handler.process_webhook(body, sign(body)).id, PAYLOAD["id"])

    def test_withdrawal_payload_parses(self):
        result = parse_payload(
            raw_body({**PAYLOAD, "type": "WITHDRAWAL", "udf": None, "txHash": None})
        )
        self.assertEqual(result.type, IpnType.WITHDRAWAL)
        self.assertIsNone(result.udf)
        self.assertIsNone(result.tx_hash)


class IsIpnFreshTest(unittest.TestCase):
    def setUp(self):
        self.webhook = parse_payload(raw_body())
        self.sent = self.webhook.timestamp

    def test_recent_is_fresh(self):
        self.assertTrue(is_ipn_fresh(self.webhook, 3600, now=self.sent + timedelta(minutes=1)))

    def test_old_is_stale(self):
        self.assertFalse(is_ipn_fresh(self.webhook, 3600, now=self.sent + timedelta(seconds=3601)))

    def test_default_outlasts_retry_schedule(self):
        self.assertTrue(is_ipn_fresh(self.webhook, now=self.sent + timedelta(hours=8)))
        self.assertFalse(is_ipn_fresh(self.webhook, now=self.sent + timedelta(hours=25)))

    def test_far_future_is_rejected(self):
        self.assertFalse(is_ipn_fresh(self.webhook, 3600, now=self.sent - timedelta(minutes=10)))
        self.assertTrue(is_ipn_fresh(self.webhook, 3600, now=self.sent - timedelta(minutes=1)))

    def test_naive_timestamp_is_rejected(self):
        naive = parse_payload(raw_body({**PAYLOAD, "timestamp": "2026-07-24T00:00:00"}))
        self.assertFalse(is_ipn_fresh(naive, now=datetime(2026, 7, 24, tzinfo=timezone.utc)))


if __name__ == "__main__":
    unittest.main()
