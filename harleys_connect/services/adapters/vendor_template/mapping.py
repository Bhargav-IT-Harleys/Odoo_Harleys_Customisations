class VendorTemplateMappingService:
    """Template for vendor-specific mapping hooks."""

    @staticmethod
    def build_order_payload(purchase_order):
        raise NotImplementedError
