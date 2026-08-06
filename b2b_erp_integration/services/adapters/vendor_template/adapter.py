from ..base_adapter import BaseAdapter
from .mapping import VendorTemplateMappingService


class VendorTemplateAdapter(BaseAdapter):
    @staticmethod
    def build_order_payload(purchase_order):
        return VendorTemplateMappingService.build_order_payload(purchase_order)

    def authenticate(self, config):
        raise NotImplementedError

    def place_order(self, config, payload):
        raise NotImplementedError

    def webhook(self, config, payload):
        raise NotImplementedError

    def search_products(self, config, query=None):
        raise NotImplementedError
