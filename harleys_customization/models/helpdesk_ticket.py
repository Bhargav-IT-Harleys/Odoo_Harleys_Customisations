from odoo import api, fields, models, _



class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    def _default_team_id(self):
        team_id = self.env['helpdesk.team'].search([('member_ids', 'in', self.env.uid)], limit=1).id
        if not team_id:
            team_id = self.env['helpdesk.team'].search([], limit=1).id
        return team_id

    department_id = fields.Many2one('hr.department', "Department", required=True)
    location_id = fields.Many2one('stock.warehouse', "Location", required=True)
    service_type_id = fields.Many2one('service.type', "Service Type", required=True)

    team_id = fields.Many2one('helpdesk.team', string='Helpdesk Team', default=_default_team_id, index=True, tracking=True)

    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id:
            self.priority = self.service_type_id.priority

    