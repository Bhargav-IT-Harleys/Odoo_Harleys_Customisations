from odoo import fields, models


class IndentCloseConfirm(models.TransientModel):
    _name = "indent.close.confirm"
    _description = "Confirm Indent Close"

    request_id = fields.Many2one(
        "indent.request",
        required=True,
        readonly=True,
    )

    def action_confirm(self):
        self.ensure_one()
        self.request_id._action_close_internal()

        return {
            "type": "ir.actions.act_window_close",
        }