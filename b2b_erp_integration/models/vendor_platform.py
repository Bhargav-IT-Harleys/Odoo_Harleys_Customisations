from odoo import fields, models


class VendorPlatform(models.Model):
    _name = 'vendor.platform'
    _description = 'Vendor Platform'

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
