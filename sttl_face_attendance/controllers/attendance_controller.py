# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.hr_attendance.controllers.main import HrAttendance as BaseHrAttendance


class HrAttendance(http.Controller):
    @http.route('/employee/images', type="json", auth="public")
    def get_employee_images(self, employee_id=None, token=None):
        def _employee_face_data(employee):
            return {
                "employee_id": employee.id,
                "image": employee.image_1920,
                "face_descriptor": employee.face_descriptor,
            }

        domain = []
        if token:
            company = BaseHrAttendance._get_company(token)
            if not company:
                return []
            domain.append(('company_id', '=', company.id))
        if employee_id:
            domain.append(('id', '=', employee_id))

        employees = request.env['hr.employee'].sudo().search(domain)
        return [_employee_face_data(employee) for employee in employees]

    @http.route('/hr_attendance/face_selection', type="jsonrpc", auth="public")
    def face_selection(self, token, employee_id, latitude=False, longitude=False):
        company = BaseHrAttendance._get_company(token)
        if company:
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if employee.company_id == company:
                employee.sudo()._attendance_action_change(BaseHrAttendance._get_geoip_response(
                    'kiosk',
                    latitude=latitude,
                    longitude=longitude,
                    device_tracking_enabled=company.attendance_device_tracking,
                ))
                return BaseHrAttendance._get_employee_info_response(employee)
        return {}
