import time

from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _must_check_identity(cls):
        session = request.session
        user = request.env(user=session.uid).user
        inactivity_timeout = user._get_lock_timeout_inactivity()
        inactivity_deadline = session.get('identity-check-next')
        if (
            inactivity_timeout
            and inactivity_deadline is not None
            and inactivity_deadline <= time.time()
        ):
            return {'logout': True}
        return None

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
