from odoo import models, fields


class StockPickingQtyMismatchConfirm(models.TransientModel):
    _name = "stock.picking.qty.mismatch.confirm"
    _description = "Confirm Demand / Trans Qty Mismatch"

    picking_id = fields.Many2one("stock.picking", required=True, readonly=True)
    mismatch_move_ids = fields.Many2many("stock.move", readonly=True)

    def action_confirm(self):
        self.ensure_one()
        result = self.picking_id.with_context(skip_qty_mismatch_confirm=True).button_validate()
        if isinstance(result, dict):
            return result
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
