from .common.exceptions import ConfigurationError, PayloadError
from .common.validators import validate_mobile_number, validate_otp
from .registry import AdapterRegistry
from . import adapters  # noqa: F401 - imports adapter modules so they register themselves.


class VendorIntegrationManager:
    """Central facade for all vendor integrations."""

    def __init__(self, config):
        self.config = config

    def _get_adapter(self):
        vendor_code = self.config.platform_id.code or self.config.platform_id.name
        adapter = AdapterRegistry.get(vendor_code or "")
        if not adapter:
            raise ConfigurationError(
                "No adapter registered for vendor '%s'." % (vendor_code or "unknown")
            )
        return adapter

    def request_otp(self):
        if not self.config.mobile_number:
            raise ConfigurationError("Mobile number is required.")
        validate_mobile_number(self.config.mobile_number)
        return self._get_adapter().request_otp(self.config)

    def verify_otp(self, otp):
        validate_otp(otp)
        return self._get_adapter().verify_otp(self.config, otp)

    def build_order_payload(self, purchase_order):
        return self._get_adapter().build_order_payload(purchase_order)

    def create_order(self, purchase_order):
        payload = self.build_order_payload(purchase_order)
        if not payload.get("po_number"):
            raise PayloadError("Purchase order number is required.")
        return self._get_adapter().create_order(self.config, payload)
