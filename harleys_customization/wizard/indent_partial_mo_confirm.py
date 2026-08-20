from odoo import fields, models


class IndentPartialMoConfirm(models.TransientModel):
    _name = "indent.partial.mo.confirm"
    _description = "Confirm Partial Indent Selection for MO Creation"

    line_ids = fields.Many2many("indent.request.line", required=True, readonly=True)

    def action_confirm(self):
        self.ensure_one()
        return self.line_ids.with_context(
            active_ids=self.line_ids.ids,
            skip_partial_mo_confirm=True,
        ).action_create_mo()

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}
