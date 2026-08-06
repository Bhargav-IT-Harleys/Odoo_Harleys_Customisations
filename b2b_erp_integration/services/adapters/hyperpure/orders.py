from ...http_client import HttpClient


class HyperpureOrderService:
    @staticmethod
    def create_order(config, payload):
        headers = {
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        }
        return HttpClient.post(config.order_url, payload, headers)
