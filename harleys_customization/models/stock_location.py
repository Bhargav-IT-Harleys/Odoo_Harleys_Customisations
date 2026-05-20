from odoo import _, api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    material_request_picking_type_id = fields.Many2one(
        'stock.picking.type', 'Material Request Operation Type', copy=True, readonly=False,
        store=True, precompute=True,
        check_company=True, index=True)

    production_transfer_picking_type_id = fields.Many2one(
        'stock.picking.type', 'Production Transfer Operation Type', copy=True, readonly=False,
        store=True, precompute=True,
        check_company=True, index=True)