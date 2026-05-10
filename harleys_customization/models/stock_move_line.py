import datetime

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    expiration_date = fields.Datetime(
        string='Expiration Date', store=True,
        compute=False,
        help='This is the date on which the goods with this Serial Number may'
        ' become dangerous and must not be consumed.')
