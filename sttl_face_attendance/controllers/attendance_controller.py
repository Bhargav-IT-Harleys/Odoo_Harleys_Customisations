# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.hr_attendance.controllers.main import HrAttendance as BaseHrAttendance
from odoo.http import request


class HrAttendance(http.Controller):
    @http.route('/employee/images', type="jsonrpc", auth="public")
    def get_employee_images(self, employee_id=None, token=None):
        if not token:
            return []

        company = BaseHrAttendance._get_company(token)
        if not company:
            return []

        domain = [('company_id', '=', company.id)]
        if employee_id:
            domain.append(('id', '=', employee_id))

        employees = request.env['hr.employee'].sudo().search(domain)
        return [
            {
                "employee_id": employee.id,
                "image": employee.image_1920,
            }
            for employee in employees
            if employee.image_1920
        ]

    @http.route('/hr_attendance/face_selection', type="jsonrpc", auth="public")
    def face_selection(
        self,
        token,
        employee_id,
        attendance_action,
        latitude=False,
        longitude=False,
    ):
        company = BaseHrAttendance._get_company(token)
        if not company:
            return {}

        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists() or employee.company_id != company:
            return {}
        if attendance_action not in ('check_in', 'check_out'):
            return {'error': 'invalid_action'}
        if (
            attendance_action == 'check_in'
            and employee.attendance_state != 'checked_out'
        ):
            return {'error': 'already_checked_in'}
        if (
            attendance_action == 'check_out'
            and employee.attendance_state != 'checked_in'
        ):
            return {'error': 'already_checked_out'}

        employee._attendance_action_change(BaseHrAttendance._get_geoip_response(
            'kiosk',
            latitude=latitude,
            longitude=longitude,
            device_tracking_enabled=company.attendance_device_tracking,
        ))
        return BaseHrAttendance._get_employee_info_response(employee)
