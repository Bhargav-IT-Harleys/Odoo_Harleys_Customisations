from odoo import api, fields, models, _



class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # ticket_id = fields.Char(string="Ticket ID", compute="_compute_ticket_id", store=True, readonly=True)
    department_id = fields.Many2one('hr.department', "Department", required=True)
    location_id = fields.Many2one('stock.warehouse', "Location", required=True)
    service_type_id = fields.Many2one('service.type', "Service Type", required=True)


    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id:
            self.priority = self.service_type_id.priority
    
    
    # @api.depends('name')
    # def _compute_ticket_id(self):
    #     for ticket in self:
    #         if ticket.name and '#' in ticket.display_name:
    #             num = ticket.display_name.split('#')[-1].strip(')')
    #             ticket.ticket_id = num
    #         else:
    #             ticket.ticket_id = False