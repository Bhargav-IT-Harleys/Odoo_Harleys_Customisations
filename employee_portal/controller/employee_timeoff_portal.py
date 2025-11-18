# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request
from odoo.exceptions import UserError


class EmployeePortal(Controller):
    """Class for Employee details"""

    @route('/my/timeoff', auth='user', website=True)
    def get_time_off(self, **post):
        """Function to get the Allocated Time Off and submit requests"""

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        # Handle Time Off Creation
        if post.get('create_timeoff'):
            if not employee:
                raise UserError("Employee record not found for the logged-in user.")

            # Create the time off request
            request.env['hr.leave'].sudo().create({
                'employee_id': employee.id,
                'holiday_status_id': int(post.get('holiday_status_id')),
                'request_date_from': post.get('date_from'),
                'request_date_to': post.get('date_to'),
                'number_of_days': float(post.get('number_of_days')),
                'state': 'confirm'
            })

        time_offs = request.env['hr.leave'].sudo().search([
            ('employee_id', '=', employee.id)
        ])

        leave_types = request.env['hr.leave.type'].sudo().search([])

        return request.render('employee_portal.portal_employee_timeoff_details', {
            'timeoffs': time_offs,
            'leave_types': leave_types
        })

    @route('/my/timeoff/request', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def request_time_off(self, **post):
        """Function to create a Time Off request from the portal"""

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if request.httprequest.method == 'POST':
            date_from = post.get('date_from')
            date_to = post.get('date_to')

            # Check for overlapping requests
            overlapping_timeoff = request.env['hr.leave'].sudo().search([
                ('employee_id', '=', employee.id),
                ('request_date_from', '<=', date_to),
                ('request_date_to', '>=', date_from),
                ('state', 'in', ['confirm', 'validate'])  # Considering confirmed or approved requests
            ], limit=1)

            if overlapping_timeoff:
                message = (
                    f"You've already booked time off which overlaps with this period:\n"
                    f"from {overlapping_timeoff.request_date_from.strftime('%d/%m/%Y')} "
                    f"to {overlapping_timeoff.request_date_to.strftime('%d/%m/%Y')} - To Approve\n"
                    f"Attempting to double-book your time off won't magically make your vacation 2x better!"
                )
                return request.render('employee_portal.portal_timeoff_success', {
                    'alert_type': 'danger',
                    'message': message
                })

            # Creating the Time Off request
            request.env['hr.leave'].sudo().create({
                'employee_id': employee.id,
                'holiday_status_id': int(post.get('holiday_status_id')),
                'request_date_from': date_from,
                'request_date_to': date_to,
                'number_of_days': float(post.get('number_of_days', 0)),
            })

            return request.render('employee_portal.portal_timeoff_success', {
                'alert_type': 'success',
                'message': "Your time off request has been successfully submitted."
            })

        # Fetch available time-off types
        timeoff_types = request.env['hr.leave.type'].sudo().search([])

        return request.render('employee_portal.portal_timeoff_request_form', {
            'employee': employee,
            'timeoff_types': timeoff_types,
        })


class TimeOffCount(portal.CustomerPortal):
    """Class for Time Off Count in Portal"""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if employee and 'timeoff_count' in counters:
            values['timeoff_count'] = request.env['hr.leave'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
        return values
