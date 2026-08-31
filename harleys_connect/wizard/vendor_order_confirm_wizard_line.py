# -*- coding: utf-8 -*-

from odoo import fields, models


class VendorOrderConfirmWizardLine(models.TransientModel):
    _name = "vendor.order.confirm.wizard.line"
    _description = "Vendor Order Confirmation - Line"

    wizard_id = fields.Many2one("vendor.order.confirm.wizard", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    product_qty = fields.Float()
    our_price = fields.Float(string="Our Price")
    vendor_product_code = fields.Char(
        help="The vendor's own product code for this item, resolved from "
             "product.supplierinfo - blank if this product isn't mapped to "
             "the vendor at all.",
    )
    vendor_price = fields.Float(
        string="Vendor Price",
        help="Filled in by the price check - blank until checked.",
    )
    price_mismatch = fields.Boolean()
    mismatch_note = fields.Char()
