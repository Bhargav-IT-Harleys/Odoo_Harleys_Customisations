class BaseAdapter:

    vendor_code = None
    # "procurement" (pushes orders out, e.g. Hyperpure) or "reporting" (pulls data in, e.g. Rista).
    category = "procurement"
    supports_pull = False

    def authenticate(self):
        raise NotImplementedError

    def place_order(self):
        raise NotImplementedError

    def build_order_payload(self, config, purchase_order, outlet=None, omit_price_product_codes=None):
        raise NotImplementedError

    def webhook(self):
        raise NotImplementedError

    def search_products(self, config, outlet_id, product_numbers=None, query=None):
        raise NotImplementedError

    def pull(self, config, **kwargs):
        """Fetch data from the vendor (reporting adapters). Not required for
        procurement adapters, which push via place_order() instead."""
        raise NotImplementedError

    @staticmethod
    def extract_refreshed_token(response):
        """Return an updated auth token found in `response`, or None if the
        vendor didn't rotate it on this call. Default: vendors that don't
        silently rotate tokens don't need to override this."""
        return None

    @staticmethod
    def translate_exception(exc):
        """Map a vendor-specific exception to one of the generic
        IntegrationError subtypes (services.common.exceptions) that the rest
        of the app catches, preserving http_status/error_code/response_body
        where the adapter's own exception carried them. Default: adapters
        that don't define their own exception hierarchy don't need to
        override this - the exception passes through unchanged."""
        return exc

    @staticmethod
    def compute_webhook_idempotency_key(payload):
        """Return a stable string identifying this webhook event for dedup,
        or None to let the controller fall back to a generic guess. Override
        when a vendor's dedup contract needs more than "one id field
        somewhere in the payload" - e.g. Hyperpure's own order_number
        legitimately repeats across different order_status values for the
        same order, so the two must be combined into one key."""
        return None
