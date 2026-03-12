from odoo import api, fields, models
from odoo.http import request

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    wage_type = fields.Selection(related="version_id.wage_type", groups="base.group_portal")

    def action_print_payslip(self):
        report = self.env['ir.actions.report']._get_report_from_name('hr_payroll.report_payslip_lang')
        return report.report_action(self)
