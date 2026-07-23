"""Exceptions for the SagaPay SDK."""

from typing import Optional, Dict, Any


class SagaPayError(Exception):
    """Base exception for SagaPay SDK."""

    def __init__(self, message: str):
        """Initialize the exception.
        
        Args:
            message: Error message
        """
        self.message = message
        super().__init__(self.message)


class ValidationError(SagaPayError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: Optional[str] = None):
        """Initialize the exception.
        
        Args:
            message: Error message
            field: Name of the field that failed validation
        """
        self.field = field
        message_with_field = f"{message}" if field is None else f"{field}: {message}"
        super().__init__(message_with_field)


class APIError(SagaPayError):
    """Raised when the SagaPay API returns an error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the exception.
        
        Args:
            message: Error message
            status_code: HTTP status code
            error_code: API error code
            response: Full API response
        """
        self.status_code = status_code
        self.error_code = error_code
        self.response = response
        message_with_code = message
        if status_code is not None:
            message_with_code = f"[{status_code}] {message}"
        if error_code is not None:
            message_with_code = f"{message_with_code} (Error: {error_code})"
        super().__init__(message_with_code)


class WebhookError(SagaPayError):
    """Raised when webhook processing fails."""

    def __init__(self, message: str):
        """Initialize the exception.
        
        Args:
            message: Error message
        """
        super().__init__(message)


class NetworkError(SagaPayError):
    """Raised when a network request fails."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """Initialize the exception.
        
        Args:
            message: Error message
            original_error: Original exception that was raised
        """
        self.original_error = original_error
        super().__init__(message)