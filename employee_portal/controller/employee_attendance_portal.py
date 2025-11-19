# -*- coding: utf-8 -*-
"""Inheriting the controller"""
from odoo.addons.portal.controllers import portal
from odoo.http import Controller, route, request
from odoo import fields, http
from odoo.exceptions import UserError

class EmployeeAttendancePortal(Controller):

    @route(['/my/attendances'], auth="user", website=True)
    def portal_attendance(self, **kwargs):
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.uid)], limit=1)

        if not employee:
            return request.render('employee_portal.not_allowed_template')

        attendances = request.env['hr.attendance'].sudo().search([('employee_id', '=', employee.id)])

        values = {
            'employee': employee,
            'attendances': attendances,
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

