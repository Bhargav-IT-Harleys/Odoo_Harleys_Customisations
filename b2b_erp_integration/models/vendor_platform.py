from odoo import fields, models


class VendorPlatform(models.Model):
    _name = 'vendor.platform'
    _description = 'Vendor Platform'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'A vendor platform code must be unique.'),
    ]
