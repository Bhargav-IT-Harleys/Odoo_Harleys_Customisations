from .api_client import HyperpureAPIClient


class HyperpureOrderService:

    @staticmethod
    def create_order(config, payload):

        headers = {
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
        }

        return HyperpureAPIClient.post(
            config.order_url,
            payload,
            headers,
        )