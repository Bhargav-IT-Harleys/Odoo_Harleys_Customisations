from odoo import models, fields, api, _

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    batch_size = fields.Float(related="product_id.batch_size", string="Batch Size")
    batch_qty = fields.Float()