from odoo import fields, models


class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    platform_id = fields.Many2one('vendor.platform')
    vendor_product_code = fields.Char()
    vendor_product_id = fields.Char()
    vendor_uom_code = fields.Char()
