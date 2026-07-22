# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class VendorConfiguration(models.Model):
    _name = "hp.configuration"
    _description = "Vendor Configuration"
    _rec_name = "name"
    name = fields.Char(
        required=True,
        default="Default Configuration",
    )

    active = fields.Boolean(default=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Vendor",
        required=True,
        domain=[
            ("supplier_rank", ">", 0),
        ],
    )

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    mobile_number = fields.Char(
        required=True,
    )

    outlet_id = fields.Char()
    vendor_code = fields.Char()
    base_url = fields.Char(required=True)
    auth_url = fields.Char(required=True)
    order_url = fields.Char(required=True)
    webhook_url = fields.Char()
    access_token = fields.Text(copy=False)
    refresh_token = fields.Text(copy=False)
    token_expiry = fields.Datetime(copy=False)
    otp_verified = fields.Boolean(default=False)
    auto_send_po = fields.Boolean()
    auto_fetch_status = fields.Boolean(default=True)

    @api.constrains("mobile_number")
    def _check_mobile(self):
        for rec in self:
            if not rec.mobile_number:
                continue

            number = rec.mobile_number.strip()
            if not number.isdigit():
                raise ValidationError(
                    "Mobile number should contain only digits."
                )

            if len(number) != 10:
                raise ValidationError(
                    "Mobile number must contain exactly 10 digits."
                )

    @api.model
    def get_active_configuration(self):
        return self.search([
            ("active", "=", True),
            ("company_id", "=", self.env.company.id),
        ], limit=1)