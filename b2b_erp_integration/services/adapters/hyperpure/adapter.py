from .auth import HyperpureAuthService
from .orders import HyperpureOrderService
from .webhook import HyperpureWebhookService
from .constants import HyperpureConstants
from .mapping import HyperpureMappingService
from ..base_adapter import BaseAdapter


class HyperpureAdapter(BaseAdapter):
    """Hyperpure implementation of the vendor adapter contract."""

    vendor_code = HyperpureConstants.VENDOR_NAME

    @staticmethod
    def request_otp(config):
        return HyperpureAuthService.request_otp(config)

    @staticmethod
    def verify_otp(config, otp):
        return HyperpureAuthService.verify_otp(config, otp)

    @staticmethod
    def create_order(config, payload):
        return HyperpureOrderService.create_order(config, payload)

    @staticmethod
    def build_order_payload(purchase_order):
        return HyperpureMappingService.build_order_payload(purchase_order)

    @staticmethod
    def build_headers(config):
        return {
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def handle_response(response):
        return {
            "status_code": getattr(response, "status_code", None),
            "text": getattr(response, "text", None),
            "json": None,
        }

    def authenticate(self, config):
        return self.request_otp(config)

    def place_order(self, config, payload):
        return self.create_order(config, payload)

    def webhook(self, config, payload):
        return HyperpureWebhookService.handle(config, payload)

    def search_products(self, config, query=None):
        return {"query": query, "vendor": HyperpureConstants.VENDOR_NAME}
