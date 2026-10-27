#!/usr/bin/env python3
"""
Example webhook handler for SagaPay notifications.

This example uses Flask to create a simple server that handles
webhook notifications from SagaPay.

To run this example:
1. Install Flask: pip install flask
2. Copy your signing secret from the dashboard (Webhooks -> Signing secret)
   into the SAGAPAY_SIGNING_SECRET environment variable
3. Run the server: python webhook_handler.py
4. Expose your server to the internet over HTTPS (e.g., using ngrok)
5. Use that URL as the ipn_url when you create deposits and withdrawals
"""

import os
import logging

from flask import Flask, request, jsonify

from sagapay import IpnType, SIGNATURE_HEADER, TransactionStatus, WebhookHandler, WebhookPayload
from sagapay.exceptions import WebhookError

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Your signing secret: dashboard -> Webhooks -> Signing secret. It is NOT your
# API secret. Notifications whose X-Sagapay-Merchant-Signature does not match
# it are rejected.
webhook_handler = WebhookHandler(
    os.environ["SAGAPAY_SIGNING_SECRET"],
    max_age_seconds=24 * 60 * 60,  # optional: refuse notifications older than a day
)

# Ids already handled. Use a database table with a unique column in
# production; this set is lost on restart.
processed_ids = set()


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle webhook notifications from SagaPay."""
    try:
        # The exact raw request body: the signature is computed over it.
        webhook = webhook_handler.process_webhook(
            request.get_data(), request.headers.get(SIGNATURE_HEADER)
        )
    except WebhookError as e:
        logger.warning("Rejected webhook: %s", e)
        return jsonify({"received": False}), 401

    logger.info(
        "Webhook received: ID=%s, Type=%s, Status=%s, Asset=%s, Amount=%s",
        webhook.id,
        webhook.type,
        webhook.status,
        webhook.asset,
        webhook.amount,
    )

    # Delivery is at-least-once, and a replayed request carries a valid
    # signature too, so act on each id only once.
    if webhook.id in processed_ids:
        return jsonify({"received": True, "duplicate": True}), 200

    # If this raises, Flask answers 500 and SagaPay retries the notification.
    handle_transaction_status(webhook)
    processed_ids.add(webhook.id)

    return jsonify({"received": True}), 200


def handle_transaction_status(webhook: WebhookPayload) -> None:
    """Handle different transaction statuses.

    Args:
        webhook: The webhook payload
    """
    if webhook.status == TransactionStatus.COMPLETED:
        # Handle completed transaction (currently the only status SagaPay sends)
        logger.info("Transaction %s completed: %s %s", webhook.id, webhook.amount, webhook.type)

        # Example business logic (note: webhook.type is uppercase IpnType):
        if webhook.type == IpnType.DEPOSIT:
            # Check webhook.asset, webhook.contract_address and webhook.amount
            # against the order before you mark it paid.
            logger.info("Updating order %s to status 'paid'", webhook.udf)
            # update_order_status(webhook.udf, "paid")
        else:  # IpnType.WITHDRAWAL
            # Update withdrawal status in your database
            logger.info("Updating withdrawal %s to status 'completed'", webhook.udf)
            # update_withdrawal_status(webhook.udf, "completed")

    else:
        # Other statuses are not currently sent via IPN, but log them
        # defensively in case new statuses are introduced
        logger.info(
            "Transaction %s is %s: %s %s",
            webhook.id,
            webhook.status,
            webhook.amount,
            webhook.type,
        )


if __name__ == "__main__":
    # Run the Flask app
    # Flask's debug server is for local testing only; never expose it.
    app.run(host="127.0.0.1", port=8080)
