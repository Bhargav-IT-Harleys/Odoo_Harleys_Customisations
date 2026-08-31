class AdapterRegistry:
    """Registry for vendor adapters."""

    _adapters = {}

    @classmethod
    def register(cls, vendor_name, adapter_cls):
        # Imported here, not at module level: adapters/__init__.py imports each
        # vendor package (to trigger its self-registration), and each vendor
        # package imports AdapterRegistry back from this module - a top-level
        # import of BaseAdapter here would make that a circular import.
        from .adapters.base_adapter import BaseAdapter
        if not issubclass(adapter_cls, BaseAdapter):
            raise TypeError("Adapter must inherit from BaseAdapter")
        cls._adapters[vendor_name.lower()] = adapter_cls

    @classmethod
    def get(cls, vendor_name):
        return cls._adapters.get(vendor_name.lower())

    @classmethod
    def list(cls):
        return list(cls._adapters.keys())
