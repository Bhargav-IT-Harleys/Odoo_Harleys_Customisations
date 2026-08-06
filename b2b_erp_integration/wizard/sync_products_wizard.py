from odoo import models


class SyncProductsWizard(models.TransientModel):
    _name = 'sync.products.wizard'
    _description = 'Sync Products Wizard'

    def action_sync(self):
        return {'type': 'ir.actions.act_window_close'}
