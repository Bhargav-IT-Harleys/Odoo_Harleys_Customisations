# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.addons.b2b_erp_integration.services.common.exceptions import (
    AuthenticationError,
    ConfigurationError,
    PayloadError,
)
from odoo.addons.b2b_erp_integration.services.manager import VendorIntegrationManager


class VendorAuthWizard(models.TransientModel):
    _name = "vendor.auth.wizard"
    _description = "Vendor Authentication"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        required=True,
    )

    account_id = fields.Many2one(
        "vendor.account",
        required=True,
    )

    otp = fields.Char(
        required=True,
    )

    def action_verify(self):

        self.ensure_one()

        purchase = self.purchase_order_id
        manager = VendorIntegrationManager(self.account_id)

        try:
            payload = manager.build_order_payload(purchase)
            response = manager.verify_otp(self.otp)
            response_data = {
                "status_code": getattr(response, "status_code", None),
                "text": getattr(response, "text", None),
            }
            purchase.write({
                "vendor_order_sent": True,
                "vendor_order_id": response_data.get("status_code") or "PENDING",
            })
            purchase.create_vendor_api_log(
                self.account_id,
                payload,
                response_data,
                response_data.get("status_code") or 200,
            )
        except (ConfigurationError, AuthenticationError, PayloadError, ValueError) as exc:
            raise UserError(str(exc)) from exc

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
