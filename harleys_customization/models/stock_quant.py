from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'
    last_count_date = fields.Date(store=True)

    adjustment_status = fields.Selection(
        [('draft', "Draft")], string="Status",
        compute='_compute_adjustment_status', store=True,
        help="Draft: a counted quantity has been entered but not yet "
             "applied to on-hand stock.")

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
    )

    @api.depends('inventory_quantity_set')
    def _compute_adjustment_status(self):
        for quant in self:
            quant.adjustment_status = 'draft' if quant.inventory_quantity_set else False
