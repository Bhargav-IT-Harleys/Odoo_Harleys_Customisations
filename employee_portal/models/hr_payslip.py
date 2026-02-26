from odoo import api, fields, models

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    wage_type = fields.Selection(related="version_id.wage_type", groups="base.group_portal")