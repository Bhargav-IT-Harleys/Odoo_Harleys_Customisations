class IntegrationError(Exception):
    """Base exception for integration errors."""


class ConfigurationError(IntegrationError):
    """Raised when a vendor configuration is missing or invalid."""


class AuthenticationError(IntegrationError):
    """Raised when authentication fails."""


class PayloadError(IntegrationError):
    """Raised when a payload cannot be built."""


class APIResponseError(IntegrationError):
    """Raised when the vendor API responds with an error."""
