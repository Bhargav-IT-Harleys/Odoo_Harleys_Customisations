from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'


    @api.depends('move_ids.state', 'move_ids.date', 'move_type')
    def _compute_scheduled_date(self):
        for picking in self:
            if not picking.id:
                continue
            moves_dates = picking.move_ids.filtered(lambda move: move.state not in ('done', 'cancel')).mapped('date')
            if picking.move_type == 'direct':
                picking.scheduled_date = default=picking.scheduled_date
            else:
                picking.scheduled_date = max(moves_dates, default=picking.scheduled_date or fields.Datetime.now())


class StockMove(models.Model):
    _inherit = 'stock.move'


    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity, reserved_quant)
        # Override quantity to 0 for GRN
        if self.picking_code == 'incoming':
            vals['quantity'] = 0
        return vals