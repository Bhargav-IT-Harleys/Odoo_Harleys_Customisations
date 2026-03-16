from odoo import api, fields, models, _



class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    department_id = fields.Many2one('hr.department', "Department", required=True)
    location_id = fields.Many2one('stock.warehouse', "Location", required=True)
    service_type_id = fields.Many2one('service.type', "Service Type", required=True)


    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id:
            self.priority = self.service_type_id.priority


    @api.model
    def default_get(self, fields_list):
        res = super(HelpdeskTicket, self).default_get(fields_list)
        user = self.env.user
        company = user.company_id

        res['company_id'] = company.id
        team = self.env['helpdesk.team'].search([('company_id', '=', company.id)], limit=1)
        if team:
            res['team_id'] = team.id
        return res


    