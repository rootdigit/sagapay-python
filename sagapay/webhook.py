"""Webhook handler for SagaPay notifications."""

import hmac
import hashlib
import json
from typing import Dict, Any, Optional, Union

from pydantic import ValidationError as PydanticValidationError

from .exceptions import WebhookError
from .models import WebhookPayload


class WebhookHandler:
    """Handler for SagaPay webhook notifications.

    Signature verification uses the optional platform-issued IPN secret
    (this is NOT your API secret). If you have not been issued an IPN
    secret, leave it unset and signature verification is skipped. Either
    way, the primary way to confirm a notification is genuine is
    Client.verify_ipn().
    """

    def __init__(self, ipn_secret: Optional[str] = None):
        """Initialize the webhook handler.

        Args:
            ipn_secret: Optional platform-issued IPN secret used to verify
                the 'X-Sagapay-Signature' header. This is NOT your API
                secret. When omitted, signature verification is skipped and
                you should confirm notifications with Client.verify_ipn().
        """
        self.ipn_secret = ipn_secret

    def process_webhook(
        self, payload: Union[str, bytes, Dict[str, Any]], signature: Optional[str] = None
    ) -> WebhookPayload:
        """Process and (when an IPN secret is configured) verify a webhook.

        The signature is only checked when an ipn_secret was provided;
        otherwise the payload is just parsed and validated. In both cases
        the primary authenticity check is Client.verify_ipn().

        Args:
            payload: Raw webhook body as str or bytes. A dict is accepted
                only when no ipn_secret is configured, because the signature
                is computed over the exact raw request body.
            signature: Signature from the 'X-Sagapay-Signature' header,
                e.g. 'sha256=<hex digest>'. Required when an ipn_secret
                is configured.

        Returns:
            WebhookPayload: The validated webhook payload

        Raises:
            WebhookError: If signature validation fails or payload is invalid
        """
        if self.ipn_secret:
            if isinstance(payload, dict):
                raise WebhookError(
                    "Signature verification requires the raw request body "
                    "(str or bytes), not a parsed dict"
                )
            if not self.verify_signature(payload, signature):
                raise WebhookError("Invalid webhook signature")

        # Parse the payload
        try:
            if isinstance(payload, (str, bytes)):
                payload_dict = json.loads(payload)
            else:
                payload_dict = payload

            return WebhookPayload.model_validate(payload_dict)
        except json.JSONDecodeError:
            raise WebhookError("Invalid JSON payload")
        except PydanticValidationError as e:
            raise WebhookError(f"Invalid webhook payload format: {str(e)}")

    def verify_signature(self, payload: Union[str, bytes], signature: Optional[str]) -> bool:
        """Verify the HMAC-SHA256 signature of a webhook payload.

        The signature is an HMAC-SHA256 hex digest of the exact raw request
        body, keyed with the platform-issued IPN secret, and is sent as
        'X-Sagapay-Signature: sha256=<hex digest>'.

        Args:
            payload: Exact raw webhook body as str or bytes
            signature: Signature from the 'X-Sagapay-Signature' header,
                with or without the 'sha256=' prefix

        Returns:
            bool: True if signature is valid, False otherwise

        Raises:
            WebhookError: If signature is missing or no IPN secret is configured
        """
        if not signature:
            raise WebhookError("Missing webhook signature")
        if not self.ipn_secret:
            raise WebhookError("No IPN secret configured for signature verification")

        if signature.startswith("sha256="):
            signature = signature[len("sha256="):]

        if isinstance(payload, str):
            payload = payload.encode('utf-8')

        computed_signature = hmac.new(
            key=self.ipn_secret.encode('utf-8'),
            msg=payload,
            digestmod=hashlib.sha256
        ).hexdigest()

        try:
            return hmac.compare_digest(computed_signature, signature)
        except TypeError:
            return False
