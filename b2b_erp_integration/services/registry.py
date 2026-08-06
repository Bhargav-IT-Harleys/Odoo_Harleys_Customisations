from .adapters.base_adapter import BaseAdapter


class AdapterRegistry:
    """Registry for vendor adapters."""

    _adapters = {}

    @classmethod
    def register(cls, vendor_name, adapter_cls):
        if not issubclass(adapter_cls, BaseAdapter):
            raise TypeError("Adapter must inherit from BaseAdapter")
        cls._adapters[vendor_name.lower()] = adapter_cls

    @classmethod
    def get(cls, vendor_name):
        return cls._adapters.get(vendor_name.lower())

    @classmethod
    def list(cls):
        return list(cls._adapters.keys())
