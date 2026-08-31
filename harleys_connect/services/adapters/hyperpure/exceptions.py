from ...common.exceptions import AuthenticationError as CommonAuthenticationError
from ...common.exceptions import APIResponseError as CommonAPIResponseError
from ...common.exceptions import PayloadError as CommonPayloadError


class HyperpureException(Exception):
    """Base class for Hyperpure-specific errors. Every concrete subclass sets
    `generic_cls` to the common IntegrationError subtype it should become at
    the adapter boundary (see HyperpureAdapter.translate_exception) - nothing
    outside this package should ever catch a HyperpureException directly."""

    generic_cls = CommonAPIResponseError

    def __init__(self, message, status_code=None, error_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.response_body = response_body


class AuthenticationError(HyperpureException):
    """OTP/token authentication failed (Hyperpure's UNAUTHORIZED_ERROR)."""
    generic_cls = CommonAuthenticationError


class InvalidRequestError(HyperpureException):
    """Generic BAD_REQUEST_ERROR with no more specific entity_type match."""
    generic_cls = CommonPayloadError


class ProductError(HyperpureException):
    """Product-level rejection: PRODUCT_NOT_AVAILABLE, PRODUCT_NOT_IN_STOCK,
    PRICE_MISMATCH_ERROR, MOQ_ERROR, MXQ_ERROR."""
    generic_cls = CommonPayloadError


class OutletAccountError(HyperpureException):
    """Account/credit rejection: ACCOUNT_CREDIT_INACTIVE, ACCOUNT_BLOCKED,
    ACCOUNT_CREDIT_INSUFFICIENT."""
    generic_cls = CommonPayloadError


class OrderValueError(HyperpureException):
    """MIN_ORDER_VALUE_ERROR."""
    generic_cls = CommonPayloadError


class MalformedResponseError(HyperpureException):
    """Response wasn't valid JSON, or didn't have the expected shape."""
    generic_cls = CommonAPIResponseError


class MissingOrderIdError(HyperpureException):
    """A successful-looking order response had no identifiable order id."""
    generic_cls = CommonAPIResponseError
