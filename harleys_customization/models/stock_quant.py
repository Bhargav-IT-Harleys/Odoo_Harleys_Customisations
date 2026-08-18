from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    adjustment_status = fields.Selection(
        [('draft', "Draft")], string="Status",
        compute='_compute_adjustment_status', store=True,
        help="Draft: a counted quantity has been entered but not yet "
             "applied to on-hand stock.")

    @api.depends('inventory_quantity_set')
    def _compute_adjustment_status(self):
        for quant in self:
            quant.adjustment_status = 'draft' if quant.inventory_quantity_set else False

    @api.model
    def action_view_inventory(self):
        action = super().action_view_inventory()
        allowed_warehouses = getattr(self.env.user, 'allowed_warehouse_ids', self.env['stock.warehouse'])
        total_warehouses = self.env['stock.warehouse'].search_count([])
        if allowed_warehouses and total_warehouses and len(allowed_warehouses) > total_warehouses / 2:
            action['context'].pop('search_default_my_count', None)
        search_view = self.sudo().env.ref('harleys_customization.quant_search_view_location_panel')
        action['search_view_id'] = (search_view.id, search_view.name)
        return action
