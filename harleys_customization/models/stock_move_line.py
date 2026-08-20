from collections import defaultdict

from odoo import api, models, _
from odoo.http import request
from odoo.tools.safe_eval import safe_eval


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model
    def action_view_moves_history(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("stock.stock_move_line_action")
        allowed_location_ids = self.env['stock.location']._get_user_allowed_location_ids().ids
        domain = safe_eval(action.get("domain") or "[]")
        action["domain"] = domain + [
            '|',
            ("location_id", "in", allowed_location_ids),
            ("location_dest_id", "in", allowed_location_ids),
        ]
        return action

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
            })