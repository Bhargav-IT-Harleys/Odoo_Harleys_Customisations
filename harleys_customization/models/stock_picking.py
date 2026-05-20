from odoo import _, api, fields, models, SUPERUSER_ID


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # def button_validate(self):
    #     for line in self.move_line_ids:
    #         if not line.expiration_date:
    #             line._compute_expiration_date()
    #     super().button_validate()
        
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


    def generate_report(self):        
        report_action = self.env.ref('stock.action_report_delivery')
        return report_action.with_user(SUPERUSER_ID).report_action(self)


class StockMove(models.Model):
    _inherit = 'stock.move'


    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity, reserved_quant)
        # Override quantity to 0 for GRN
        if self.picking_code == 'incoming':
            vals['quantity'] = 0
        return vals