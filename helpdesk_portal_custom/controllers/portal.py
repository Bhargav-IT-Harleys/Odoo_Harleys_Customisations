# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.portal.controllers.portal import CustomerPortal


class HelpdeskPortalCustom(CustomerPortal):

    def _get_helpdesk_teams(self):
        return request.env['helpdesk.team'].sudo().search(
            [('active', '=', True), ('company_id', 'in', [company_id.id for company_id in request.env.user.company_ids])], order='name asc'
        )

    def _get_service_type(self):
        return request.env['service.type'].sudo().search([])

    def _get_locations(self):
        return request.env['stock.warehouse'].sudo().search(
            [('active', '=', True), ('company_id', 'in', [company_id.id for company_id in request.env.user.company_ids])], order='name asc'
        )

    def _get_hr_department(self):
        return request.env['hr.department'].sudo().search([])

    @http.route('/helpdesk', type='http', auth='user', website=True, methods=['GET'])
    def portal_helpdesk_ticket_new(self, **kwargs):
        service_types = self._get_service_type()
        locations = self._get_locations()
        departments = self._get_hr_department()
        teams = self._get_helpdesk_teams()
        values = {
            'full_name': request.env.user.name,
            'teams': teams,
            'service_types': service_types,
            'locations': locations,
            'departments': departments,
            'phone_number': request.env.user.phone,
            'email': request.env.user.email,
            'error': {},
            'error_message': [],
        }
        return request.render(
            'helpdesk_portal_custom.portal_form_custom', values
        )
