from odoo import fields, models


class VendorOutlet(models.Model):
    _name = 'vendor.outlet'
    _description = 'Vendor Outlet'

    name = fields.Char(required=True)
    platform_id = fields.Many2one('vendor.platform', required=True)
    outlet_code = fields.Char()
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
