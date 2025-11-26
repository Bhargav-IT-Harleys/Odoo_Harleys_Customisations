# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request
from odoo import fields, http
from odoo.exceptions import UserError
from odoo.tools.translate import _
from collections import defaultdict

class EmployeeAttendancePortal(Controller):


    def _employee_get_searchbar_groupby(self):
        return {
            'none': {'label': _('None'), 'sequence': 10},
            'month': {'label': _('Month'), 'sequence': 20},
            'year': {'label': _('Year'), 'sequence': 30},
        }

    @route(['/my/attendances'], auth="user", website=True)
    def portal_attendance(self, groupby='none', **kwargs,):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.uid)], limit=1)

        if not employee:
            return request.render('employee_portal.not_allowed_template')

        employee_domain = [('employee_id', '=', employee.id)]
        attendances = request.env['hr.attendance'].sudo().search(employee_domain)
        grouped_by_month = defaultdict(list)
        grouped_by_year = defaultdict(list)

        searchbar_groupby = dict(sorted(self._employee_get_searchbar_groupby().items(), key=lambda item: item[1]['sequence']))

        if groupby == 'month':
            for attendance_month in attendances:
                month_key = attendance_month.date.strftime("%B %Y")
                grouped_by_month[month_key].append({
                    'check_in': attendance_month.check_in.strftime("%Y-%m-%d %H:%M:%S"),
                    'check_out': attendance_month.check_out.strftime("%Y-%m-%d %H:%M:%S"),
                    'worked_hours': attendance_month.worked_hours or 0,
                    'overtime_hours': attendance_month.overtime_hours or '00:00',
                })

        if groupby == 'year':
            for attendance_year in attendances:
                year_key = attendance_year.date.strftime("%Y")
                grouped_by_year[year_key].append({
                    'check_in': attendance_year.check_in.strftime("%Y-%m-%d %H:%M:%S"),
                    'check_out': attendance_year.check_out.strftime("%Y-%m-%d %H:%M:%S"),
                    'worked_hours': attendance_year.worked_hours or 0,
                    'overtime_hours': attendance_year.overtime_hours or '00:00',
                })


        values = {
            'employee': employee,
            'attendances': attendances,
            'searchbar_groupby': searchbar_groupby,
            'groupby': groupby,
            'grouped_by_month': grouped_by_month,
            'grouped_by_year': grouped_by_year,
        }
        return request.render('employee_portal.portal_attendance_template', values)

    @route(['/my/attendance/check_in'], type='http', auth='user', website=True)
    def check_in(self, **kwargs):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.uid)], limit=1)
        if not employee:
            raise UserError("Employee not found.")

        # Check if already checked in
        last_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        if last_attendance:
            raise UserError("You are already checked in. Please check out before checking in again.")

        # Create a new attendance entry
        request.env['hr.attendance'].sudo().create({
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
        })
        return request.redirect('/my/attendances')

    @route(['/my/attendance/check_out'], type='http', auth='user', website=True)
    def check_out(self, **kwargs):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.uid)], limit=1)
        if not employee:
            raise UserError("Employee not found.")

        # Check if there is an active check-in
        last_attendance = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False)
        ], limit=1)
        if not last_attendance:
            raise UserError("You are not checked in.")

        # Update check-out time
        last_attendance.sudo().write({'check_out': fields.Datetime.now()})
        return request.redirect('/my/attendances')

class AttendanceCount(portal.CustomerPortal):
    """Class for Time Off Count in Portal"""

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)

        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', request.env.uid)
        ], limit=1)

        if employee and 'attendance_count' in counters:
            values['attendance_count'] = request.env['hr.attendance'].sudo().search_count([
                ('employee_id', '=', employee.id)
            ])
        return values

