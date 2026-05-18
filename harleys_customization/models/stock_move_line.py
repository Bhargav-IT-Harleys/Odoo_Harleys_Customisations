import datetime

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    expiration_date = fields.Datetime(
        string='Expiration Date', store=True,
        compute='_compute_expiration_date_custom',
        help='This is the date on which the goods with this Serial Number may'
        ' become dangerous and must not be consumed.')


    @api.depends('product_id', 'lot_id.expiration_date', 'picking_id.scheduled_date')
    def _compute_expiration_date_custom(self):
        for move_line in self:
            if move_line.picking_type_use_existing_lots:
                if move_line.lot_id.expiration_date:
                    move_line.expiration_date = move_line.lot_id.expiration_date
                elif move_line.picking_type_use_create_lots:
                    if move_line.product_id.use_expiration_date:
                        if not move_line.expiration_date:
                            from_date = move_line.picking_id.scheduled_date or fields.Datetime.today()
                            move_line.expiration_date = from_date + datetime.timedelta(days=move_line.product_id.expiration_time)
                    else:
                        move_line.expiration_date = False