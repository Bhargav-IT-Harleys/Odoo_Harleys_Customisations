from ..base_adapter import BaseAdapter
from .auth import RistaAuthService
from .client import RistaReportService
from .constants import RistaConstants


class RistaAdapter(BaseAdapter):
    """Rista implementation of the vendor adapter contract - reporting only,
    no purchase-order push."""

    vendor_code = RistaConstants.VENDOR_NAME
    category = "reporting"
    supports_pull = True

    def authenticate(self, config):
        # Rista has no separate login/token-exchange call - every request signs its
        # own short-lived JWT from the configured key pair, so "authenticating"
        # just means the key pair is present and can produce a signed header.
        return RistaAuthService.get_auth_headers("GET", config.api_key, config.secret_key)

    def pull(self, config, report_id=None, params=None, **kwargs):
        return RistaReportService.fetch_report(config, report_id, params)
