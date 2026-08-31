from ...common.exceptions import APIResponseError as CommonAPIResponseError
from ..base_adapter import BaseAdapter
from .auth import HyperpureAuthService
from .constants import HyperpureConstants
from .exceptions import HyperpureException
from .mapping import HyperpureMappingService
from .orders import HyperpureOrderService
from .response import HyperpureResponseParser
from .webhook import HyperpureWebhookService


class HyperpureAdapter(BaseAdapter):
    """Hyperpure implementation of the vendor adapter contract."""

    vendor_code = HyperpureConstants.VENDOR_NAME
    category = "procurement"

    def get_outlet_phone_numbers(self, config, outlet_id, page_no=None):
        return HyperpureAuthService.get_outlet_phone_numbers(config, outlet_id, page_no=page_no)

    def request_otp(self, config, user_id):
        return HyperpureAuthService.request_otp(config, user_id)

    def verify_otp(self, config, otp, user_id):
        response = HyperpureAuthService.verify_otp(config, otp, user_id)
        return HyperpureResponseParser.parse_auth_response(response)

    def build_order_payload(self, config, purchase_order, outlet=None, omit_price_product_codes=None):
        return HyperpureMappingService.build_order_payload(
            config, purchase_order, outlet=outlet, omit_price_product_codes=omit_price_product_codes
        )

    def place_order(self, config, payload):
        # Hyperpure's team asked us to call place_order directly - the
        # validate_order_placement pre-check is failing on their side for
        # reasons unrelated to our payload, so skip it per their instruction.
        response = HyperpureOrderService.place_order(config, payload)
        order_id = HyperpureResponseParser.parse_order_response(response, payload.get("external_order_id"))
        return order_id, response

    def search_products(self, config, outlet_id, product_numbers=None, query=None):
        response = HyperpureOrderService.search_products(
            config, outlet_id, search_query=query, product_numbers=product_numbers
        )
        return HyperpureResponseParser.parse_search_response(response)

    def authenticate(self, config, user_id):
        return self.request_otp(config, user_id)

    def webhook(self, config, payload, headers=None):
        if headers is not None and not HyperpureWebhookService.verify_signature(config, headers):
            raise PermissionError("Invalid or missing x-hp-api-key header on Hyperpure webhook.")
        return HyperpureWebhookService.handle(config, payload)

    @staticmethod
    def extract_refreshed_token(response):
        # Hyperpure's spec: an expired token is silently renewed and returned
        # in the "authorization" header of whatever call used it.
        return HyperpureResponseParser.parse_auth_header(response)

    @staticmethod
    def translate_exception(exc):
        if not isinstance(exc, HyperpureException):
            return exc
        generic_cls = exc.generic_cls or CommonAPIResponseError
        return generic_cls(
            str(exc), http_status=exc.status_code, error_code=exc.error_code, response_body=exc.response_body
        )

    @staticmethod
    def compute_webhook_idempotency_key(payload):
        # Hyperpure's own idempotency guidance: dedupe on (order_number,
        # order_status) together - the same order_number legitimately
        # recurs across PLACED/DISPATCHED/DELIVERED/etc, each a real event.
        orders = payload.get("orders")
        order = orders[0] if isinstance(orders, list) and orders else payload
        order_number = order.get("order_number")
        order_status = order.get("order_status")
        if order_number and order_status:
            return f"{order_number}:{order_status}"
        return None
