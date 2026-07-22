# -*- coding: utf-8 -*-

from odoo import fields, models


class HyperpureOrderLog(models.Model):
    _name = "hp.order.log"
    _description = "Hyperpure Order Log"
    _order = "create_date desc"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        string="Purchase Order",
        required=True,
        ondelete="cascade",
    )

    configuration_id = fields.Many2one(
        "hp.configuration",
        string="Configuration",
    )

    vendor_id = fields.Many2one(
        "res.partner",
        related="purchase_order_id.partner_id",
        store=True,
    )

    request_payload = fields.Text(
        string="Request JSON",
    )

    response_payload = fields.Text(
        string="Response JSON",
    )

    http_status = fields.Integer()

    hp_order_id = fields.Char(
        string="Hyperpure Order ID",
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