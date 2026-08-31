from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vendor_sync_enabled = fields.Boolean(default=False)
