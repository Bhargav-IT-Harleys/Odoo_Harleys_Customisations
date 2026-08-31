import json

from odoo import http
from odoo.http import request

from odoo.addons.harleys_connect.services.common.logging import get_logger
from odoo.addons.harleys_connect.services.common.payload import redact_payload
from odoo.addons.harleys_connect.services.registry import AdapterRegistry
from odoo.addons.harleys_connect.services import adapters  # noqa: F401

_logger = get_logger(__name__)

_EVENT_ID_KEYS = ("event_id", "id", "webhook_id", "order_id", "vendor_order_id", "external_order_id")
_OUTLET_ID_KEYS = ("outlet_id", "outlet", "outletId", "buyer_outlet_id")


def _first_order(payload):
    orders = payload.get("orders")
    return orders[0] if isinstance(orders, list) and orders else payload


def _extract_event_id(payload):
    for source in (payload, _first_order(payload)):
        for key in _EVENT_ID_KEYS:
            value = source.get(key)
            if value:
                return str(value)
    return None


def _extract_outlet_id(payload):
    for source in (payload, _first_order(payload)):
        for key in _OUTLET_ID_KEYS:
            value = source.get(key)
            if value:
                return str(value)
    return None


def _extract_purchase_order_id(result):
    if isinstance(result, list):
        for entry in result:
            if isinstance(entry, dict) and entry.get("purchase_order_id"):
                return entry["purchase_order_id"]
    return None


class VendorWebhookController(http.Controller):
    """One generic route for every vendor's webhook - vendor_code selects the
    adapter, everything vendor-specific (signature scheme, payload shape)
    stays inside that adapter. This controller only handles what's the same
    for any vendor: dedup, outlet validation, and audit logging."""

    @http.route(
        "/harleys_connect/webhook/<string:vendor_code>",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def webhook(self, vendor_code, **post):
        payload = request.httprequest.get_json(silent=True) or {}

        adapter_cls = AdapterRegistry.get(vendor_code)
        if not adapter_cls:
            _logger.warning("Webhook received for unsupported vendor: %s", vendor_code)
            return self._respond("unsupported vendor", 404)

        account = request.env["vendor.account"].sudo().get_active_account(vendor_code=vendor_code)
        if not account:
            _logger.warning("Webhook received for vendor without active account: %s", vendor_code)
            return self._respond("vendor account not configured", 404)

        adapter = adapter_cls()
        event_id = adapter.compute_webhook_idempotency_key(payload) or _extract_event_id(payload)
        idempotency_key = f"{vendor_code}:{event_id}" if event_id else None
        if idempotency_key:
            existing = request.env["vendor.webhook.log"].sudo().search(
                [("idempotency_key", "=", idempotency_key)], limit=1
            )
            if existing:
                _logger.info("Duplicate webhook for %s (event %s) - returning cached result.", vendor_code, event_id)
                return self._respond(existing.response_payload or "ok", existing.http_status or 200)

        outlet_id = _extract_outlet_id(payload)
        if outlet_id:
            outlet = request.env["vendor.outlet"].sudo().search([
                ("vendor_account_id", "=", account.id),
                ("outlet_id", "=", outlet_id),
            ], limit=1)
            if not outlet:
                self._log(account, vendor_code, payload, "invalid outlet", 400, idempotency_key, event_id, outlet_id, "failed")
                return self._respond("invalid outlet", 400)

        try:
            result = adapter.webhook(account, payload, request.httprequest.headers)
        except PermissionError as exc:
            _logger.warning("Webhook signature check failed for %s: %s", vendor_code, exc)
            self._log(account, vendor_code, payload, str(exc), 401, idempotency_key, event_id, outlet_id, "failed")
            return self._respond("invalid signature", 401)
        except Exception as exc:
            _logger.exception("Webhook processing failed for %s", vendor_code)
            self._log(account, vendor_code, payload, str(exc), 500, idempotency_key, event_id, outlet_id, "failed")
            return self._respond("error", 500)

        purchase_order_id = _extract_purchase_order_id(result)
        self._log(account, vendor_code, payload, result, 200, idempotency_key, event_id, outlet_id, "processed", purchase_order_id)
        _logger.info("Processed vendor webhook for %s: %s", vendor_code, result)
        return self._respond("ok", 200)

    @staticmethod
    def _respond(body, status):
        text = body if isinstance(body, str) else json.dumps(redact_payload(body))
        return request.make_response(text, status=status, headers={"Content-Type": "text/plain"})

    @staticmethod
    def _log(account, vendor_code, payload, response, http_status, idempotency_key, event_id, outlet_id, status, purchase_order_id=None):
        response_text = response if isinstance(response, str) else json.dumps(redact_payload(response), indent=4)
        request.env["vendor.webhook.log"].sudo().create({
            "platform_id": account.platform_id.id,
            "account_id": account.id,
            "vendor_code": vendor_code,
            "vendor_event_id": event_id,
            "idempotency_key": idempotency_key,
            "outlet_id": outlet_id,
            "purchase_order_id": purchase_order_id,
            "request_payload": json.dumps(redact_payload(payload), indent=4),
            "response_payload": response_text,
            "http_status": http_status,
            "status": status,
            "error_message": response if status == "failed" and isinstance(response, str) else None,
        })
