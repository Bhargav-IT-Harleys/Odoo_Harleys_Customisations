from odoo import api, fields, models, _



class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    department_id = fields.Many2one('hr.department', "Department", required=True)
    location_id = fields.Many2one('stock.warehouse', "Location", required=True)
    service_type_id = fields.Many2one('service.type', "Service Type", required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', tracking=True, index=True)

    @api.onchange('service_type_id')
    def _onchange_service_type_id(self):
        if self.service_type_id:
            self.priority = self.service_type_id.priority

    @api.depends('ticket_ref', 'partner_name')
    @api.depends_context('with_partner')
    def _compute_display_name(self):
        display_partner_name = self.env.context.get('with_partner', False)
        ticket_with_name = self.filtered('name')
        for ticket in ticket_with_name:
            name = ticket.name
            if ticket.ticket_ref:
                name += f' (#{ticket.ticket_ref})'
            if display_partner_name and ticket.partner_name:
                name += f' - {ticket.partner_name}'
            ticket.display_name = name
            ticket.partner_id = self.env['res.partner'].sudo().search([('name', '=', ticket.partner_name)], limit=1).id
        return super(HelpdeskTicket, self - ticket_with_name)._compute_display_name()

    