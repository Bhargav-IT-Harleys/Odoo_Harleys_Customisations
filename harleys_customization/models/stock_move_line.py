import datetime
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.http import request
from odoo.tools.sql import column_exists, create_column

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_batch_over_reservation()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if 'quantity' in vals or 'lot_id' in vals:
            self._check_batch_over_reservation()
        return result

    def _check_batch_over_reservation(self):
        if not request:
            return
        affected = self.filtered(lambda l: l.lot_id and l.quantity_product_uom)
        if not affected:
            return
        quants = self.env['stock.quant'].sudo().search([
            ('lot_id', 'in', affected.lot_id.ids),
            ('location_id', 'in', affected.location_id.ids),
        ])
        available_by_key = defaultdict(float)
        for quant in quants:
            available_by_key[(quant.lot_id.id, quant.location_id.id)] += quant.available_quantity
        overbooked = [
            f"{line.product_id.display_name} / {line.lot_id.name}"
            for line in affected
            if available_by_key[(line.lot_id.id, line.location_id.id)] < 0
        ]
        if overbooked:
            self.env.user._bus_send('simple_notification', {
                'type': 'warning',
                'title': _("Some batches were fully claimed by someone else"),
                'message': _(
                    "The following batches had less available than shown when "
                    "you added them, and may now be over-reserved - please "
                    "double check: %s", ', '.join(overbooked),
                ),
                'sticky': True,
            })

    # expiration_date = fields.Datetime(
    #     string='Expiration Date', store=True,
    #     compute='_compute_expiration_date_custom',
    #     help='This is the date on which the goods with this Serial Number may'
    #     ' become dangerous and must not be consumed.')

    # @api.depends('product_id', 'lot_id.expiration_date', 'picking_id.scheduled_date', 'quant_id')
    # def _compute_expiration_date_custom(self):
    #     for move_line in self:
    #         if move_line.picking_type_use_existing_lots:                
    #             if lot_id := move_line.quant_id.lot_id or move_line.lot_id:
    #                 move_line.expiration_date = lot_id.expiration_date
    #             elif move_line.picking_type_use_create_lots:
    #                 if move_line.product_id.use_expiration_date:
    #                     if not move_line.expiration_date:
    #                         from_date = move_line.picking_id.scheduled_date or fields.Datetime.today()
    #                         move_line.expiration_date = from_date + datetime.timedelta(days=move_line.product_id.expiration_time)
    #                 else:
    #                     move_line.expiration_date = False

    # @api.depends('product_id', 'lot_id.expiration_date', 'picking_id.scheduled_date')
    # def _compute_expiration_date(self):
    #     for move_line in self:
    #         # if move_line.picking_type_use_existing_lots:                
    #         if move_line.lot_id.expiration_date:
    #             move_line.expiration_date = move_line.lot_id.expiration_date
    #         elif move_line.picking_type_use_create_lots:
    #             if move_line.product_id.use_expiration_date:
    #                 if not move_line.expiration_date:
    #                     from_date = move_line.picking_id.scheduled_date or fields.Datetime.today()
    #                     move_line.expiration_date = from_date + datetime.timedelta(days=move_line.product_id.expiration_time)
    #             else:
    #                 move_line.expiration_date = False