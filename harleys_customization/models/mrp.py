from odoo import models, fields, api, _

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    batch_size = fields.Float(related="product_id.batch_size", string="Batch Size")
    batch_qty = fields.Float()
    section = fields.Many2one(related="product_id.product_tmpl_id.section", string="Section", store=True)

class StockMove(models.Model):
    _inherit = "stock.move"

    mo_name = fields.Char(related='raw_material_production_id.name', string="MO Ref.")
    mo_product_qty = fields.Float(related="raw_material_production_id.product_qty", string="MO Qty")
    mo_date_start = fields.Datetime(related='raw_material_production_id.date_start', string="MO Schedule Date")
    mo_section = fields.Many2one('production.section', related='raw_material_production_id.section', string="Prob. Sect.")
    mo_product_uom_id = fields.Many2one('uom.uom', related='raw_material_production_id.product_uom_id', string="MO Prod. UOM")
    mo_product_id = fields.Many2one('product.product', string="MO Product", related='raw_material_production_id.product_id', store=True, readonly=True)
    categ_id = fields.Many2one('product.category', string="MO lines Prod. Catg.", related='product_id.categ_id', store=True, readonly=True)