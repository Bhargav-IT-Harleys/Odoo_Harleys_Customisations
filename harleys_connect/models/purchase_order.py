# -*- coding: utf-8 -*-

import json

from odoo.exceptions import UserError
from odoo import api, fields, models

from odoo.addons.harleys_connect.services.common.exceptions import IntegrationError
from odoo.addons.harleys_connect.services.common.payload import redact_payload
from odoo.addons.harleys_connect.services.manager import VendorIntegrationManager


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_order_sent = fields.Boolean(
        default=False,
        readonly=True,
    )

    vendor_order_id = fields.Char(
        readonly=True,
        help="Our own order reference as sent to the vendor "
             "(external_order_id) - Hyperpure's place_order response doesn't "
             "return a separate vendor-generated id.",
    )

    vendor_order_number = fields.Char(
        readonly=True,
        help="The vendor's own order number, learned from their first "
             "order-status webhook call (not available at place_order time).",
    )

    vendor_order_status = fields.Char(readonly=True)

    vendor_api_log_count = fields.Integer(
        compute="_compute_vendor_api_log_count",
    )

    vendor_webhook_log_count = fields.Integer(
        compute="_compute_vendor_webhook_log_count",
    )

    def _compute_vendor_api_log_count(self):

        log_model = self.env["vendor.api.log"]

        for order in self:
            order.vendor_api_log_count = log_model.search_count([
                ("purchase_order_id", "=", order.id)
            ])

    def _compute_vendor_webhook_log_count(self):

        log_model = self.env["vendor.webhook.log"]

        for order in self:
            order.vendor_webhook_log_count = log_model.search_count([
                ("purchase_order_id", "=", order.id)
            ])

    def action_send_to_vendor(self):
        self.ensure_one()

        account = self.env["vendor.account"].get_active_account(
            company=self.company_id,
            partner=self.partner_id,
        )
        if not account:
            raise UserError("No active vendor account found for this supplier.")
        if not account.access_token:
            raise UserError(
                "This vendor account isn't authenticated yet. Open it under "
                "Harley's Connect > Vendor Accounts and click Authenticate first."
            )

        return self.env["vendor.order.confirm.wizard"].open_for_order(self, account)

    def _send_to_vendor(self, account, outlet, omit_price_product_codes=None):
        self.ensure_one()

        manager = VendorIntegrationManager(account)
        payload = None
        try:
            payload = manager.build_order_payload(self, outlet=outlet, omit_price_product_codes=omit_price_product_codes)
            order_id, response = manager.send_order(payload)
        except IntegrationError as exc:
            self.create_vendor_api_log(
                account,
                payload or {},
                exc.response_body if exc.response_body is not None else {"error": str(exc)},
                exc.http_status,
                state="failed",
                error_message=str(exc),
            )
            # The UserError below rolls back this transaction - without an
            # explicit commit here, the log row above would be wiped out
            # along with it, so a failed send would leave no trace at all.
            self.env.cr.commit()
            error = UserError(str(exc))
            # If this failure was a price mismatch, the vendor's real price
            # is embedded in their structured error data - surface it so the
            # caller (the confirm wizard) can show it instead of just a dead
            # end, since there's no other way to learn it (search_products is
            # broken on Hyperpure's sandbox for our account).
            error.price_corrections = self._extract_price_corrections(exc.response_body)
            raise error from exc

        self.write({
            "vendor_order_sent": True,
            "vendor_order_id": order_id,
        })
        self.create_vendor_api_log(
            account,
            payload,
            self._safe_response_body(response),
            response.status_code,
            vendor_order_id=order_id,
            state="success",
            sent_on=fields.Datetime.now(),
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Vendor Integration",
                "message": "Purchase Order sent successfully.",
                "type": "success",
                "sticky": False,
            },
        }

    @staticmethod
    def _extract_price_corrections(response_body):
        """{vendor_product_code: vendor's real price} from a PRODUCT_PRICE_MISMATCH
        rejection's structured error data - the only place this vendor's real
        price is ever available to us right now."""
        if not isinstance(response_body, dict):
            return {}
        error = response_body.get("error")
        if not isinstance(error, dict):
            return {}
        data = error.get("data")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                data = None
        if not isinstance(data, list):
            return {}

        corrections = {}
        for item in data:
            if isinstance(item, dict) and item.get("error_type") == "PRODUCT_PRICE_MISMATCH":
                code, price = item.get("entity_value"), item.get("expected_value")
                if code and price is not None:
                    corrections[str(code)] = price
        return corrections

    @staticmethod
    def _safe_response_body(response):
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    def create_vendor_api_log(
        self,
        account,
        payload,
        response,
        status,
        vendor_order_id=None,
        state="draft",
        error_message=None,
        sent_on=None,
    ):
        values = {
            "purchase_order_id": self.id,
            "account_id": account.id,
            "request_payload": json.dumps(redact_payload(payload), indent=4),
            "response_payload": json.dumps(redact_payload(response), indent=4),
            "http_status": status,
            "state": state,
        }
        if vendor_order_id is not None:
            values["vendor_order_id"] = vendor_order_id
        if error_message is not None:
            values["error_message"] = error_message
        if sent_on is not None:
            values["sent_on"] = sent_on
        self.env["vendor.api.log"].create(values)

    def action_view_vendor_api_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vendor API Logs",
            "res_model": "vendor.api.log",
            "view_mode": "list,form",
            "domain": [("purchase_order_id", "=", self.id)],
            "context": {
                "default_purchase_order_id": self.id,
            },
        }

    def action_view_vendor_webhook_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vendor Webhook Logs",
            "res_model": "vendor.webhook.log",
            "view_mode": "list,form",
            "domain": [("purchase_order_id", "=", self.id)],
        }

    show_vendor_send_button = fields.Boolean(
        compute="_compute_show_vendor_send_button"
    )

    @api.depends("partner_id", "state", "vendor_order_sent")
    def _compute_show_vendor_send_button(self):
        account_model = self.env["vendor.account"]

        companies = self.mapped("company_id")
        partners = self.mapped("partner_id")
        active_accounts = account_model.search([
            ("active", "=", True),
            ("company_id", "in", companies.ids),
            ("vendor_partner_id", "in", partners.ids),
        ])
        account_by_key = {
            (account.company_id.id, account.vendor_partner_id.id): account
            for account in active_accounts
        }

        for order in self:
            account = account_by_key.get((order.company_id.id, order.partner_id.id))
            order.show_vendor_send_button = (
                order.state == "purchase"
                and not order.vendor_order_sent
                and bool(account)
                and bool(account.access_token)
            )
