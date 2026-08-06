# -*- coding: utf-8 -*-

import json

from odoo.exceptions import UserError
from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    vendor_order_sent = fields.Boolean(
        default=False,
        readonly=True,
    )

    vendor_order_id = fields.Char(
        readonly=True,
    )

    vendor_api_log_count = fields.Integer(
        compute="_compute_vendor_api_log_count",
    )

    def _compute_vendor_api_log_count(self):

        log_model = self.env["vendor.api.log"]

        for order in self:
            order.vendor_api_log_count = log_model.search_count([
                ("purchase_order_id", "=", order.id)
            ])

    def action_send_to_vendor(self):

        self.ensure_one()

        account = self.env["vendor.account"].get_active_account(
            company=self.company_id,
            partner=self.partner_id,
        )

        if not account:
            raise UserError(
                "No active vendor account found for this supplier."
            )

        return {
            "type": "ir.actions.act_window",
            "name": "OTP Verification",
            "res_model": "vendor.auth.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
                "default_account_id": account.id,
            },
        }

    def create_vendor_api_log(
        self,
        account,
        payload,
        response,
        status,
    ):

        self.env["vendor.api.log"].create({
            "purchase_order_id": self.id,
            "account_id": account.id,
            "request_payload": json.dumps(
                payload,
                indent=4,
            ),
            "response_payload": json.dumps(
                response,
                indent=4,
            ),
            "http_status": status,
        })

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
    
    show_vendor_send_button = fields.Boolean(
        compute="_compute_show_vendor_send_button"
    )

    @api.depends("partner_id", "state", "vendor_order_sent")
    def _compute_show_vendor_send_button(self):
        account_model = self.env["vendor.account"]
        for order in self:
            order.show_vendor_send_button = (
                order.state == "purchase"
                and not order.vendor_order_sent
                and bool(account_model.get_active_account(
                    company=order.company_id,
                    partner=order.partner_id,
                ))
            )
