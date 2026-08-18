from odoo import _, api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    material_request_picking_type_id = fields.Many2one(
        'stock.picking.type', 'Material Request Operation Type', copy=True, readonly=False,
        store=True,
        check_company=True, index=True)

    production_transfer_picking_type_id = fields.Many2one(
        'stock.picking.type', 'Production Transfer Operation Type', copy=True, readonly=False,
        store=True,
        check_company=True, index=True)

    def _get_user_allowed_location_ids(self):
        user = self.env.user
        allowed_warehouses = getattr(user, 'allowed_warehouse_ids', self.env['stock.warehouse'])
        if allowed_warehouses:
            warehouse_view_loc_ids = allowed_warehouses.mapped('view_location_id').ids
            return self.search([
                ('location_id', 'child_of', warehouse_view_loc_ids),
                ('usage', '=', 'internal'),
                ('active', '=', True),
            ])
        company_id = self.env.company.id
        return self.search([
            ('usage', '=', 'internal'),
            ('active', '=', True),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', company_id),
        ])
