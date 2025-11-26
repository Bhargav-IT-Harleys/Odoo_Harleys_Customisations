# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request
from odoo.exceptions import UserError
from odoo.tools.translate import _
from collections import defaultdict

class EmployeePortal(Controller):
    """Class for Employee details"""


    def _timeoff_get_searchbar_groupby(self):
        return {
            'none': {'label': _('None'), 'sequence': 10},
            'month': {'label': _('Month'), 'sequence': 20},
            'year': {'label': _('Year'), 'sequence': 30},
        }

    @route('/my/timeoff', auth='user', website=True)
    def get_time_off(self, groupby='none', **post):
        """Function to get the Allocated Time Off and submit requests"""

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        grouped_by_month = defaultdict(list)
        grouped_by_year = defaultdict(list)

        searchbar_groupby = dict(sorted(self._timeoff_get_searchbar_groupby().items(), key=lambda item: item[1]['sequence']))

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

        if groupby == 'month':
            for time_offs_month in time_offs:
                month_key = time_offs_month.create_date.strftime("%B %Y")
                grouped_by_month[month_key].append({
                    'holiday_status_id': time_offs_month.holiday_status_id.name,
                    'date_from': time_offs_month.date_from.strftime("%Y-%m-%d %I:%M:%S %p"),
                    'date_to': time_offs_month.date_to.strftime("%Y-%m-%d %I:%M:%S %p"),
                    'duration_display': time_offs_month.duration_display,
                    'state': time_offs_month.state,
                })

        if groupby == 'year':
            for time_offs_year in time_offs:
                year_key = time_offs_year.create_date.strftime("%Y")
                grouped_by_year[year_key].append({
                    'holiday_status_id': time_offs_year.holiday_status_id.name,
                    'date_from': time_offs_year.date_from.strftime("%Y-%m-%d %I:%M:%S %p"),
                    'date_to': time_offs_year.date_to.strftime("%Y-%m-%d %I:%M:%S %p"),
                    'duration_display': time_offs_year.duration_display,
                    'state': time_offs_year.state,
                })

        leave_types = request.env['hr.leave.type'].sudo().search([])

        return request.render('employee_portal.portal_employee_timeoff_details', {
            'timeoffs': time_offs,
            'leave_types': leave_types,
            'searchbar_groupby': searchbar_groupby,
            'groupby': groupby,
            'grouped_by_month': grouped_by_month,
            'grouped_by_year': grouped_by_year,
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

            time_float = lambda t: int(t.split(":")[0]) + int(t.split(":")[1]) / 60

            from datetime import datetime

            days = (datetime.strptime(date_to,"%Y-%m-%d") - datetime.strptime(date_from,"%Y-%m-%d")).days

            # Creating the Time Off request
            hr_leave = request.env['hr.leave'].sudo().create({
                'employee_id': employee.id,
                'holiday_status_id': int(post.get('holiday_status_id')),
                'request_date_from': date_from,
                'request_date_to': date_to,
                'request_hour_from':time_float(post.get('request_hour_from')), 
                'request_hour_to': time_float(post.get('request_hour_to')),
                'number_of_days': float(days),
            })


            return request.render('employee_portal.portal_timeoff_success', {
                'alert_type': 'success',
                'message': "Your time off request has been successfully submitted."
            })

        # Fetch available time-off types
        timeoff_types = request.env['hr.leave.type'].search([
            '|',
                ('requires_allocation', '=', False),
                ('has_valid_allocation', '=', True),
        ])

        return request.render('employee_portal.portal_timeoff_request_form', {
            'employee': employee,
            'timeoff_types': timeoff_types,
            'time_visible': True, #if leave.holiday_status_id.request_unit_hours else False,
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
