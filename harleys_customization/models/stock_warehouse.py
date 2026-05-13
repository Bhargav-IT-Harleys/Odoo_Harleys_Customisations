from odoo import _, api, fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    code = fields.Char('Short Name', required=True, size=8, help="Short name used to identify your warehouse")