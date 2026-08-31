class IntegrationError(Exception):
    """Base exception for integration errors.

    Carries optional structured detail (http_status/error_code/response_body)
    so an adapter's own vendor-specific exception can be translated into one
    of these generic types (see BaseAdapter.translate_exception) without
    losing that detail - callers that want it can read it off the exception,
    everyone else just uses str(exc)."""

    def __init__(self, message, http_status=None, error_code=None, response_body=None):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code
        self.response_body = response_body


class ConfigurationError(IntegrationError):
    """Raised when a vendor configuration is missing or invalid."""


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""


class PayloadError(IntegrationError):
    """Raised when a payload cannot be built."""


class APIResponseError(IntegrationError):
    """Raised when the vendor API responds with an error."""


class NetworkError(IntegrationError):
    """Raised when the vendor's server can't be reached at all (DNS failure,
    connection refused, timeout) - distinct from APIResponseError, which
    means the vendor did respond, just with an error."""
