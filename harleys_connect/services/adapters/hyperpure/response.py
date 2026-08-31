import json

from .exceptions import (
    AuthenticationError,
    HyperpureException,
    InvalidRequestError,
    MalformedResponseError,
    OrderValueError,
    OutletAccountError,
    ProductError,
)

# Keyed by Hyperpure's own documented error_type strings (see the
# "Error Code Scenarios" spec) - not by HTTP status code or a keyword guess
# against error_message, both of which are unreliable: Hyperpure wraps every
# validation failure the same way regardless of status, and error_message
# text isn't a stable contract.
_ERROR_TYPE_MAP = {
    "ACCOUNT_CREDIT_INACTIVE": OutletAccountError,
    "ACCOUNT_BLOCKED": OutletAccountError,
    "ACCOUNT_CREDIT_INSUFFICIENT": OutletAccountError,
    "PRODUCT_NOT_AVAILABLE": ProductError,
    "PRODUCT_NOT_IN_STOCK": ProductError,
    "PRODUCT_PRICE_MISMATCH": ProductError,
    "PRODUCT_MINIMUM_ORDER_QUANTITY": ProductError,
    "PRODUCT_MAXIMUM_ORDER_QUANTITY": ProductError,
    "MIN_ORDER_VALUE_ERROR": OrderValueError,
}

# validate_order_placement and place_order both confirm success via a
# free-text message, not a structured {"error": {...}} absence or a
# dedicated order-id field - no order id of any kind is returned. We use our
# own external_order_id as the record of what was sent, rather than trying to
# parse one out of theirs. Confirmed live: calling place_order directly
# (skipping the validate pre-check, per Hyperpure's own instruction) returns
# "Order request accepted successfully..." - not "Order placed successfully"
# as documented - likely reflecting their async acceptance-then-processing
# flow. Matching both phrasings.
_VALIDATION_SUCCESS_PHRASES = ("order verified successfully", "order request accepted successfully")
_ORDER_PLACED_PHRASES = ("order placed successfully", "order request accepted successfully")


class HyperpureResponseParser:

    @staticmethod
    def parse_auth_header(response):
        headers = getattr(response, "headers", None) or {}
        token = headers.get("authorization") or headers.get("Authorization")
        if not token:
            return None
        token = str(token).strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token or None

    @staticmethod
    def parse_auth_response(response):
        status = getattr(response, "status_code", None)
        if status is None or status >= 400:
            HyperpureResponseParser._raise_from_error_body(response, status)
        token = HyperpureResponseParser.parse_auth_header(response)
        if not token:
            raise AuthenticationError(
                "Hyperpure did not return an authorization token in the response header.",
                status_code=status,
            )
        return token

    @staticmethod
    def parse_validate_response(response):
        status = getattr(response, "status_code", None)
        if status is None or status >= 400:
            HyperpureResponseParser._raise_from_error_body(response, status)

        body = HyperpureResponseParser._safe_json(response)
        response_obj = body.get("response") if isinstance(body, dict) else None
        message = str((response_obj or {}).get("message", "")).strip().lower()
        if not message or not any(phrase in message for phrase in _VALIDATION_SUCCESS_PHRASES):
            raise InvalidRequestError(
                f"Hyperpure rejected the order at validation: {message or 'no message returned.'}",
                status_code=status,
                response_body=body,
            )

    @staticmethod
    def parse_order_response(response, external_order_id=None):
        status = getattr(response, "status_code", None)
        body = HyperpureResponseParser._safe_json(response)
        if (status is None or status >= 400) or (isinstance(body, dict) and body.get("error")):
            HyperpureResponseParser._raise_from_error_body(response, status, body)

        response_obj = body.get("response") if isinstance(body, dict) else None
        message = str((response_obj or {}).get("message", "")).strip()
        if not message or not any(phrase in message.lower() for phrase in _ORDER_PLACED_PHRASES):
            raise MalformedResponseError(
                f"Unexpected place_order response: {message or body}", status_code=status, response_body=body
            )

        # Hyperpure's success response has no order-id field to extract -
        # our own external_order_id (what we sent them) is the record.
        return str(external_order_id) if external_order_id else "ACCEPTED"

    @staticmethod
    def parse_search_response(response):
        status = getattr(response, "status_code", None)
        body = HyperpureResponseParser._safe_json(response)
        if (status is None or status >= 400) or (isinstance(body, dict) and body.get("error")):
            HyperpureResponseParser._raise_from_error_body(response, status, body)

        response_obj = body.get("response") if isinstance(body, dict) else None
        products = (response_obj or {}).get("Products") or []
        return [
            {
                "product_number": str(product.get("ProductNumber")),
                # MarketPrice already reflects the negotiated contract price
                # when PriceType == "CONTRACT_PRICE" - always the right field
                # to compare against, no extra branching needed.
                "price": product.get("MarketPrice"),
                "name": product.get("Name"),
            }
            for product in products
            if isinstance(product, dict)
        ]

    @staticmethod
    def _safe_json(response):
        try:
            return response.json()
        except ValueError:
            return None

    @staticmethod
    def _raise_from_error_body(response, status, body=None):
        if body is None:
            body = HyperpureResponseParser._safe_json(response)
        error = body.get("error") if isinstance(body, dict) else None

        if not error:
            text = getattr(response, "text", "") or ""
            raise HyperpureException(
                f"Hyperpure returned HTTP {status}: {text[:500]}", status_code=status, response_body=body
            )

        code = error.get("code")
        message = error.get("message") or "Hyperpure request failed."
        raw_data = error.get("data")
        if isinstance(raw_data, str):
            # Hyperpure sometimes double-encodes this field as a JSON string
            # instead of a nested array - confirmed live on a real
            # PRODUCT_PRICE_MISMATCH response.
            try:
                raw_data = json.loads(raw_data)
            except ValueError:
                raw_data = None
        details = [item for item in (raw_data or []) if isinstance(item, dict)]

        if details:
            message += "\n" + "\n".join(
                "- {}: {}".format(
                    item.get("entity_name") or item.get("entity_value") or item.get("entity_type") or "?",
                    item.get("error_message") or item.get("error_type") or "",
                )
                for item in details
            )

        error_types = {item.get("error_type") for item in details}
        exc_cls = next(
            (_ERROR_TYPE_MAP[error_type] for error_type in error_types if error_type in _ERROR_TYPE_MAP),
            None,
        )
        if exc_cls is None:
            exc_cls = AuthenticationError if code == "UNAUTHORIZED_ERROR" else InvalidRequestError

        raise exc_cls(message, status_code=status, error_code=code, response_body=body)
