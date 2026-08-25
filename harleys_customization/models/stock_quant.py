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

    def _location_gate_search_view_id(self):
        search_view = self.sudo().env.ref('harleys_customization.quant_search_view_location_panel')
        return (search_view.id, search_view.name)

    @api.model
    def action_view_inventory(self):
        action = super().action_view_inventory()
        allowed_warehouses = getattr(self.env.user, 'allowed_warehouse_ids', self.env['stock.warehouse'])
        total_warehouses = self.env['stock.warehouse'].search_count([])
        if allowed_warehouses and total_warehouses and len(allowed_warehouses) > total_warehouses / 2:
            action['context'].pop('search_default_my_count', None)
        action['search_view_id'] = self._location_gate_search_view_id()
        return action

    @api.model
    def action_view_quants(self):
        action = super().action_view_quants()
        if not self.env.context.get('search_default_internal_loc'):
            return action
        gated_view_by_base = {
            self.sudo().env.ref('stock.view_stock_quant_tree').id:
                self.sudo().env.ref('harleys_customization.view_stock_quant_tree_location_gate').id,
            self.sudo().env.ref('stock.view_stock_quant_tree_editable').id:
                self.sudo().env.ref('harleys_customization.view_stock_quant_tree_editable_location_gate').id,
        }
        gated_view_id = gated_view_by_base.get(action['view_id'], action['view_id'])
        action['view_id'] = gated_view_id
        action['views'] = [
            (gated_view_id if view_type == 'list' else view_id, view_type)
            for view_id, view_type in action['views']
        ]
        action['search_view_id'] = self._location_gate_search_view_id()
        return action
