# -*- coding: utf-8 -*-

import json

from odoo import fields, models
from odoo.exceptions import UserError
from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    hp_order_sent = fields.Boolean(
        default=False,
        readonly=True,
    )

    hp_order_id = fields.Char(
        readonly=True,
    )

    hp_log_count = fields.Integer(
        compute="_compute_hp_log_count",
    )

    def _compute_hp_log_count(self):

        log_model = self.env["hp.order.log"]

        for order in self:
            order.hp_log_count = log_model.search_count([
                ("purchase_order_id", "=", order.id)
            ])

    def action_send_to_hyperpure(self):

        self.ensure_one()
        if "hyperpure" not in (self.partner_id.name or "").lower():
            raise UserError(
                "Selected vendor is not a Hyperpure vendor."
            )

        configuration = self.env[
            "hp.configuration"
        ].get_active_configuration()

        if not configuration:
            raise UserError(
                "No Hyperpure configuration found."
            )

        return {
            "type": "ir.actions.act_window",
            "name": "OTP Verification",
            "res_model": "hp.otp.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_purchase_order_id": self.id,
                "default_configuration_id": configuration.id,
            },
        }

    def prepare_hyperpure_payload(self):
        self.ensure_one()
        lines = []
        for line in self.order_line:
            lines.append({
                "product": line.product_id.display_name,
                "qty": line.product_qty,
                "price": line.price_unit,
                "uom": line.product_uom.name,
            })

        payload = {
            "po_number": self.name,
            "vendor": self.partner_id.name,
            "lines": lines,
        }

        return payload

    def create_hp_log(
        self,
        configuration,
        payload,
        response,
        status,
    ):

        self.env["hp.order.log"].create({
            "purchase_order_id": self.id,
            "configuration_id": configuration.id,
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

    def action_view_hp_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hyperpure Logs",
            "res_model": "hp.order.log",
            "view_mode": "list,form",
            "domain": [("purchase_order_id", "=", self.id)],
            "context": {
                "default_purchase_order_id": self.id,
            },
        }
    
    show_hyperpure_button = fields.Boolean(
        compute="_compute_show_hyperpure_button"
    )

    @api.depends("partner_id", "partner_id.name", "state", "hp_order_sent")
    def _compute_show_hyperpure_button(self):
        for order in self:
            vendor_name = (order.partner_id.name or "").lower()
            order.show_hyperpure_button = (
                order.state == "purchase"
                and "hyperpure" in vendor_name
                and not order.hp_order_sent
            )