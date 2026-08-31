import requests

from .common.exceptions import ConfigurationError, NetworkError, PayloadError
from .common.validators import validate_otp
from .registry import AdapterRegistry
from . import adapters  # noqa: F401 - imports adapter modules so they register themselves.


class VendorIntegrationManager:
    """Central facade for all vendor integrations. Vendor-neutral by design:
    this file must never import or name a specific vendor - anything
    vendor-specific belongs in that vendor's adapter package."""

    def __init__(self, config):
        self.config = config
        self._adapter = None

    def _get_adapter(self):
        if self._adapter is not None:
            return self._adapter
        vendor_code = self.config.platform_id.code or self.config.platform_id.name
        adapter_cls = AdapterRegistry.get(vendor_code or "")
        if not adapter_cls:
            raise ConfigurationError(
                "No adapter registered for vendor '%s'." % (vendor_code or "unknown")
            )
        self._adapter = adapter_cls()
        return self._adapter

    def _call(self, adapter, method_name, *args, **kwargs):
        try:
            return getattr(adapter, method_name)(*args, **kwargs)
        except requests.exceptions.RequestException as exc:
            raise NetworkError(f"Couldn't reach the vendor's server: {exc}") from exc
        except Exception as exc:
            raise adapter.translate_exception(exc) from exc

    def get_outlet_phone_numbers(self, outlet_id):
        adapter = self._get_adapter()
        if not getattr(adapter, "get_outlet_phone_numbers", None):
            raise ConfigurationError("This vendor doesn't support phone-number lookup.")
        return self._call(adapter, "get_outlet_phone_numbers", self.config, outlet_id)

    def request_otp(self, **kwargs):
        # Different vendors' auth flows take different identifiers (Hyperpure:
        # user_id from the phone-lookup step); passed through as kwargs rather
        # than hardcoding a shape here, so this stays vendor-neutral.
        adapter = self._get_adapter()
        return self._call(adapter, "request_otp", self.config, **kwargs)

    def verify_otp(self, otp, **kwargs):
        validate_otp(otp)
        adapter = self._get_adapter()
        token = self._call(adapter, "verify_otp", self.config, otp, **kwargs)
        if token and token != self.config.access_token:
            self.config.write({"access_token": token})
        return token

    def build_order_payload(self, purchase_order, outlet=None, omit_price_product_codes=None):
        return self._get_adapter().build_order_payload(
            self.config, purchase_order, outlet=outlet, omit_price_product_codes=omit_price_product_codes
        )

    def search_products(self, outlet_id, product_numbers=None, query=None):
        adapter = self._get_adapter()
        return self._call(adapter, "search_products", self.config, outlet_id, product_numbers=product_numbers, query=query)

    def send_order(self, payload):
        """Send an already-built payload. Split out from create_order() so a
        caller can hold the payload as its own local variable before calling
        this - if this raises, that variable is still bound and loggable,
        unlike `payload, order_id, response = create_order(...)`, where a
        failure partway through never binds `payload` at all."""
        if not payload.get("products"):
            raise PayloadError("At least one order line with a mapped vendor product is required.")
        adapter = self._get_adapter()
        order_id, response = self._call(adapter, "place_order", self.config, payload)
        self.capture_token(response)
        return order_id, response

    def create_order(self, purchase_order, outlet=None, omit_price_product_codes=None):
        payload = self.build_order_payload(purchase_order, outlet=outlet, omit_price_product_codes=omit_price_product_codes)
        order_id, response = self.send_order(payload)
        return payload, order_id, response

    def capture_token(self, response):
        """Persist an auth token found in `response`, if the adapter knows how
        to find one. Covers a vendor silently rotating the token on any call
        (Hyperpure's documented behaviour: an expired token gets auto-renewed
        and returned in that same call's response header)."""
        adapter = self._get_adapter()
        token = adapter.extract_refreshed_token(response)
        if token and token != self.config.access_token:
            self.config.write({"access_token": token})
        return token
