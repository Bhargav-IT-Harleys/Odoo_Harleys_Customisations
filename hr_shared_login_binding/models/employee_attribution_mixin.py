from odoo import api, models, _
from odoo.http import request


class EmployeeAttributionMixin(models.AbstractModel):
    _name = 'hr.employee.attribution.mixin'
    _description = "Logs the acting employee (not just the logged-in account) on create/write"

    def _get_acting_employee(self):
        if not request:
            # No web request (cron, RPC, import, ...): nothing to attribute.
            return self.env['hr.employee']
        employee_id = request.session.get('employee_binding_id')
        if employee_id:
            return self.env['hr.employee'].sudo().browse(employee_id).exists()
        # Individual, non-shared login: the account is already 1:1 with an
        # employee, so attribution is unambiguous without a session binding.
        return self.env.user.employee_id

    def _post_employee_attribution(self, action):
        employee = self._get_acting_employee()
        if not employee:
            return
        for record in self:
            record.message_post(body=_(
                "%(action)s by %(employee)s, via account %(account)s.",
                action=action, employee=employee.name, account=self.env.user.name,
            ))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._post_employee_attribution(_("Created"))
        return records

    def write(self, vals):
        result = super().write(vals)
        self._post_employee_attribution(_("Updated"))
        return result
