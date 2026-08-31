from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    vendor_default_api_url = fields.Char()
