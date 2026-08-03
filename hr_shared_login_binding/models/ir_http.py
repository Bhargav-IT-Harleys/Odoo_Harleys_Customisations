from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        session_info = super().session_info()
        if request.session.uid and self.env.user._is_internal():
            employee_id = request.session.get('employee_binding_id')
            if employee_id:
                employee = self.env['hr.employee'].sudo().browse(employee_id).exists()
            else:
                employee = self.env.user.employee_id
            session_info['harleys_acting_employee_name'] = employee.name if employee else False

            session_info['harleys_force_company_selection'] = bool(
                request.session.get('harleys_company_selection_pending'))
        return session_info
