from odoo import fields, models


class StockPickingCloseConfirm(models.TransientModel):
    _name = "stock.picking.close.confirm"
    _description = "Confirm Internal Transfer Close"

    picking_id = fields.Many2one(
        "stock.picking",
        required=True,
        readonly=True,
    )

    def action_confirm(self):
        self.ensure_one()
        result = self.picking_id.with_context(skip_internal_transfer_cancel_confirm=True).action_cancel()
        if isinstance(result, dict):
            return result
        return {
            "type": "ir.actions.act_window_close",
        }
