from odoo import api, fields, models, _

TICKET_PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    department_id = fields.Many2one('hr.department', "Department", required=True)
    location_id = fields.Many2one('stock.warehouse', "Location", required=True)
    service_type_id = fields.Many2one('service.type', "Service Type", required=True)
    priority = fields.Selection(TICKET_PRIORITY, string='Priority', default='0',readonly=True, tracking=True, compute='_compute_priority', store=True)

    @api.depends('service_type_id')
    def _compute_priority(self):
        if self.service_type_id:
            self.priority = self.service_type_id.priority

    