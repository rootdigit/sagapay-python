"""Webhook handler for SagaPay notifications."""

import hmac
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union

from pydantic import ValidationError as PydanticValidationError

from .exceptions import WebhookError
from .models import WebhookPayload


SIGNATURE_HEADER = "X-Sagapay-Merchant-Signature"
"""The header that carries an IPN's signature."""

DEFAULT_MAX_AGE_SECONDS = 24 * 60 * 60
"""Default for is_ipn_fresh(): 24 hours."""

# How far ahead of this machine's clock a timestamp may be before it is
# treated as invalid rather than as clock drift.
_MAX_CLOCK_SKEW = timedelta(minutes=5)

_HEX_SHA256 = re.compile(r"[0-9a-fA-F]{64}")


def is_ipn_fresh(
    payload: WebhookPayload,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
    now: Optional[datetime] = None,
) -> bool:
    """Whether a notification's timestamp is recent enough to act on.

    A guard against an old, validly signed notification being replayed. The
    timestamp is set when the transaction completes and stays the same on
    every retry, so keep max_age_seconds longer than the retry schedule
    (about 7.5 hours). A notification resent from the dashboard also keeps
    its original timestamp, and is rejected here once it is older than the
    limit.

    This is a secondary check. The main defence against replays is to
    process each notification id only once.

    Args:
        payload: A parsed webhook payload
        max_age_seconds: Oldest age to accept. Defaults to 24 hours.
        now: The current time, for tests. Defaults to the system clock.

    Returns:
        bool: False if the timestamp is older than max_age_seconds, more
        than 5 minutes in the future, or has no timezone
    """
    sent = payload.timestamp
    if sent.tzinfo is None:
        return False
    now = now or datetime.now(timezone.utc)
    return sent <= now + _MAX_CLOCK_SKEW and now - sent <= timedelta(seconds=max_age_seconds)


class WebhookHandler:
    """Verifies and parses SagaPay webhook notifications.

    Each notification is signed with your signing secret. Copy it from the
    dashboard: Webhooks -> Signing secret. It is NOT your API secret.

    Only the X-Sagapay-Merchant-Signature header is checked. The old
    platform-wide X-Sagapay-Signature header is retired and not accepted.
    """

    def __init__(self, signing_secret: str, *, max_age_seconds: Optional[float] = None):
        """Initialize the webhook handler.

        Args:
            signing_secret: Your signing secret from the dashboard's
                Webhooks page, used to verify X-Sagapay-Merchant-Signature.
            max_age_seconds: When set, process_webhook() also rejects
                notifications older than this (see is_ipn_fresh()). Keep it
                above the ~7.5 hour retry schedule; 86400 (24 hours) is a
                sensible value.

        Raises:
            ValueError: If signing_secret is empty
        """
        if not signing_secret:
            raise ValueError(
                "signing_secret is required: copy it from the dashboard's Webhooks page"
            )
        self.signing_secret = signing_secret
        self.max_age_seconds = max_age_seconds

    def process_webhook(
        self, payload: Union[str, bytes], signature: Optional[str]
    ) -> WebhookPayload:
        """Verify and parse a webhook.

        Args:
            payload: The exact raw request body as str or bytes. The
                signature is computed over these bytes, so do not pass a
                parsed or re-serialized body.
            signature: Value of the X-Sagapay-Merchant-Signature header,
                e.g. 'sha256=<hex digest>'

        Returns:
            WebhookPayload: The validated webhook payload

        Raises:
            WebhookError: If the signature is missing or wrong, the
                payload is invalid, or (with max_age_seconds) it is stale
        """
        if not isinstance(payload, (str, bytes)):
            raise WebhookError(
                "Signature verification requires the raw request body "
                "(str or bytes), not a parsed object"
            )
        if not self.verify_signature(payload, signature):
            raise WebhookError("Invalid webhook signature")

        webhook = parse_payload(payload)
        if self.max_age_seconds is not None and not is_ipn_fresh(webhook, self.max_age_seconds):
            raise WebhookError("Webhook timestamp is outside the allowed age")
        return webhook

    def verify_signature(self, payload: Union[str, bytes], signature: Optional[str]) -> bool:
        """Verify the X-Sagapay-Merchant-Signature of a webhook payload.

        The header is 'sha256=' followed by the HMAC-SHA256 hex digest of
        the exact raw request body, keyed with your signing secret.

        Args:
            payload: Exact raw webhook body as str or bytes
            signature: Value of the X-Sagapay-Merchant-Signature header,
                with or without the 'sha256=' prefix

        Returns:
            bool: True if the signature is valid, False otherwise

        Raises:
            WebhookError: If the signature is missing
        """
        if not signature:
            raise WebhookError("Missing webhook signature")

        signature = signature.strip()
        if signature[:7].lower() == "sha256=":
            signature = signature[7:]
        if not _HEX_SHA256.fullmatch(signature):
            return False

        if isinstance(payload, str):
            payload = payload.encode("utf-8")

        computed = hmac.new(
            key=self.signing_secret.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).digest()
        return hmac.compare_digest(computed, bytes.fromhex(signature))


def parse_payload(payload: Union[str, bytes, Dict[str, Any]]) -> WebhookPayload:
    """Parse a webhook body WITHOUT checking its signature.

    Use WebhookHandler.process_webhook() for requests you receive; this is
    for bodies you have already verified, or stored ones.

    Raises:
        WebhookError: If the payload is not valid JSON or not a webhook
    """
    try:
        payload_dict = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        return WebhookPayload.model_validate(payload_dict)
    except json.JSONDecodeError:
        raise WebhookError("Invalid JSON payload")
    except PydanticValidationError as e:
        raise WebhookError(f"Invalid webhook payload format: {str(e)}")
