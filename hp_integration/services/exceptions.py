class HyperpureError(Exception):
    """Base Hyperpure exception."""


class AuthenticationError(HyperpureError):
    """Authentication failed."""


class APIConnectionError(HyperpureError):
    """Unable to connect to Hyperpure."""


class OrderCreationError(HyperpureError):
    """Order creation failed."""