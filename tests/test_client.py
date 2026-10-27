"""Tests for request headers and redirect handling, against a local server."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from sagapay import APIError, Client


WITHDRAWAL = {
    "network_type": "BEP20",
    "contract_address": "0",
    "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "amount": "0.5",
    "ipn_url": "https://example.com/ipn",
}


class _Api(BaseHTTPRequestHandler):
    """Stand-in for the API: records requests; /create-withdrawal redirects
    when the server's `redirect` flag is set."""

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.server.seen.append((self.path, dict(self.headers)))
        if self.server.redirect and self.path == "/create-withdrawal":
            self.send_response(307)
            self.send_header("Location", "/elsewhere")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps({"id": "w-1", "status": "PENDING", "fee": "0"}).encode()
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ClientRequestTest(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Api)
        self.server.seen = []
        self.server.redirect = False
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.client = Client("key", "secret", base_url=base_url, timeout=5)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def header(self, index, name):
        headers = {k.lower(): v for k, v in self.server.seen[index][1].items()}
        return headers.get(name.lower())

    def test_idempotency_key_is_sent(self):
        result = self.client.create_withdrawal(WITHDRAWAL, idempotency_key="payout-123")
        self.assertEqual(result.id, "w-1")
        self.assertEqual(self.header(0, "Idempotency-Key"), "payout-123")
        self.assertEqual(self.header(0, "x-api-key"), "key")

    def test_no_idempotency_key_by_default(self):
        self.client.create_withdrawal(WITHDRAWAL)
        self.assertIsNone(self.header(0, "Idempotency-Key"))

    def test_redirects_are_not_followed(self):
        self.server.redirect = True
        with self.assertRaises(APIError) as caught:
            self.client.create_withdrawal(WITHDRAWAL)
        self.assertEqual(caught.exception.status_code, 307)
        self.assertEqual([path for path, _ in self.server.seen], ["/create-withdrawal"])


if __name__ == "__main__":
    unittest.main()
