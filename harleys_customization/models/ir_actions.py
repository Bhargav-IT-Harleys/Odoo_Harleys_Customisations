from odoo import models, fields

class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    limit = fields.Integer(default=100, help='Default limit for the list view')

    def init(self):
        self.env.cr.execute("""
            UPDATE ir_act_window
            SET "limit" = 100
            WHERE "limit" = 80
        """)
