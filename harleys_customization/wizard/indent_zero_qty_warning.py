from odoo import models, fields, _


class IndentZeroQtyWarning(models.TransientModel):
    _name = "indent.zero.qty.warning"
    _description = "Zero Demand Quantity Warning"

    request_id = fields.Many2one(
        "indent.request",
        required=True,
        readonly=True,
    )

    zero_line_ids = fields.Many2many(
        "indent.request.line",
        string="Zero Demand Lines",
        readonly=True,
    )

    def action_delete_zero_lines(self):
        self.ensure_one()

        self.request_id.line_ids.filtered(
            lambda l: (l.product_qty or 0.0) <= 0
        ).unlink()

        return {
            "type": "ir.actions.act_window_close",
        }

    def action_delete_and_continue(self):
        self.ensure_one()

        zero_lines = self.zero_line_ids.filtered(
            lambda l: (l.product_qty or 0.0) <= 0
        )
        if zero_lines:
            zero_lines.unlink()

        self.request_id._action_sent_internal()
        return {
            "type": "ir.actions.act_window_close",
        }

    def action_cancel(self):
        return {
            "type": "ir.actions.act_window_close",
        }