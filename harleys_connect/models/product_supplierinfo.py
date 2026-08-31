from odoo import fields, models


class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    # The vendor's product identifier is Odoo's own standard `product_code`
    # field (see purchase/product) - no custom field needed for that. This
    # module only adds what core doesn't already cover: which connector
    # platform this mapping is for, and the vendor's UoM code.
    platform_id = fields.Many2one(
        'vendor.platform',
        string='Vendor Platform',
        help="Which connector this mapping applies to, e.g. Hyperpure.",
    )
    vendor_uom_code = fields.Char(string='Vendor UoM Code')
