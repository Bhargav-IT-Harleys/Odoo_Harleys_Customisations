from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    user_id = fields.Many2one(tracking=True)
