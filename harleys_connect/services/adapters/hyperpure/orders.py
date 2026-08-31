from urllib.parse import urlencode

from ...http_client import HttpClient
from .auth import HyperpureAuthService, _as_int
from .constants import HyperpureConstants


class HyperpureOrderService:

    @staticmethod
    def _authenticated_headers(config):
        # Our token is shape-consistent with Mode B (a bare opaque secret,
        # no "Bearer " prefix ever present in the raw header - Mode A's JWT
        # example is dot-separated and Bearer-prefixed). Mode B's own sample
        # cURL for authenticated calls has no Authorization header at all -
        # only ApiAccessKey + ClientSecret + X-AccountId. Not tried literally
        # as-is before (previous attempts always mixed in Authorization).
        headers = {
            "ApiAccessKey": config.api_access_key,
            "Content-Type": "application/json",
            "ClientSecret": config.access_token,
        }
        if getattr(config, "account_id", False):
            headers["X-AccountId"] = str(_as_int(config.account_id))
        return headers

    @staticmethod
    def search_products(config, outlet_id, search_query=None, product_numbers=None):
        url = HyperpureAuthService._url(config, HyperpureConstants.SEARCH_PRODUCTS_PATH)
        params = {"outlet_id": outlet_id}
        if search_query:
            params["search_query"] = search_query
        if product_numbers:
            params["product_numbers"] = product_numbers
        return HttpClient.get(f"{url}?{urlencode(params, doseq=True)}", HyperpureOrderService._authenticated_headers(config))

    @staticmethod
    def validate_order_placement(config, payload):
        # Hyperpure requires this call before place_order - confirmed directly
        # with their team, not in the original integration spec doc.
        url = HyperpureAuthService._url(config, HyperpureConstants.VALIDATE_ORDER_PATH)
        return HttpClient.post(url, payload, HyperpureOrderService._authenticated_headers(config))

    @staticmethod
    def place_order(config, payload):
        url = HyperpureAuthService._url(config, HyperpureConstants.PLACE_ORDER_PATH)
        return HttpClient.post(url, payload, HyperpureOrderService._authenticated_headers(config))
