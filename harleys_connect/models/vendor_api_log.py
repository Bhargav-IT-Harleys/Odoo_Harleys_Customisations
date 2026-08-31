# -*- coding: utf-8 -*-

from odoo import fields, models


class VendorApiLog(models.Model):
    _name = "vendor.api.log"
    _description = "Vendor API Log"
    _order = "create_date desc"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        required=True,
        ondelete="cascade",
    )

    account_id = fields.Many2one(
        "vendor.account",
        string="Vendor Account",
    )

    vendor_id = fields.Many2one(
        "res.partner",
        related="purchase_order_id.partner_id",
        store=True,
    )

    request_payload = fields.Text(
        string="Request JSON",
        groups="harleys_connect.group_connect_manager",
    )

    response_payload = fields.Text(
        string="Response JSON",
        groups="harleys_connect.group_connect_manager",
    )

    http_status = fields.Integer()

    vendor_order_id = fields.Char(
        string="Vendor Order ID",
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("success", "Success"),
        ("failed", "Failed"),
    ], default="draft")

    error_message = fields.Text()

    sent_on = fields.Datetime()

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
