from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection([('x_p_o', 'Purchase Order (External PO)'), ('i_p_o', 'Internal Transfer (Internal PO)')], string='Purchase type')