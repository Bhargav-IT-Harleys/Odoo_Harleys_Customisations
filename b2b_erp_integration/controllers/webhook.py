from odoo import http
from odoo.http import request
from odoo.addons.b2b_erp_integration.services.common.logging import get_logger
from odoo.addons.b2b_erp_integration.services.registry import AdapterRegistry
from odoo.addons.b2b_erp_integration.services import adapters  # noqa: F401

_logger = get_logger(__name__)


class VendorWebhookController(http.Controller):

    @http.route(
        "/b2b_erp_integration/webhook/<string:vendor_code>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def webhook(self, vendor_code, **post):
        payload = request.httprequest.get_json(silent=True) or {}
        adapter = AdapterRegistry.get(vendor_code)
        if not adapter:
            _logger.warning("Webhook received for unsupported vendor: %s", vendor_code)
            return request.make_response(
                "unsupported vendor",
                status=404,
                headers={"Content-Type": "text/plain"},
            )

        account = request.env["vendor.account"].sudo().get_active_account(
            vendor_code=vendor_code
        )
        if not account:
            _logger.warning("Webhook received for vendor without active account: %s", vendor_code)
            return request.make_response(
                "vendor account not configured",
                status=404,
                headers={"Content-Type": "text/plain"},
            )

        adapter().webhook(account, payload)
        _logger.info("Received vendor webhook payload for %s: %s", vendor_code, payload)
        return request.make_response("ok", headers={"Content-Type": "text/plain"})
