from ...http_client import HttpClient
from .constants import HyperpureConstants


class HyperpureOrderService:
    @staticmethod
    def _build_url(config):
        if getattr(config, 'order_url', False):
            return config.order_url
        base_url = getattr(config, 'base_url', False) or HyperpureConstants.DEFAULT_BASE_URL
        return f"{base_url.rstrip('/')}{HyperpureConstants.ORDER_PATH}"

    @staticmethod
    def create_order(config, payload):
        headers = {
            "Authorization": f"Bearer {getattr(config, 'access_token', '')}",
            "Content-Type": "application/json",
        }
        return HttpClient.post(HyperpureOrderService._build_url(config), payload, headers)
