# -*- coding: utf-8 -*-

from odoo import fields, http
from odoo.addons.hr_attendance.controllers.main import HrAttendance as BaseHrAttendance
from odoo.http import request


class HrAttendance(http.Controller):
    @staticmethod
    def _create_face_check_in(employee, action_date, geo_information=None):
        vals = {
            'employee_id': employee.id,
            'check_in': action_date,
        }
        if geo_information:
            vals.update({
                'in_%s' % key: geo_information[key]
                for key in geo_information
            })
        return request.env['hr.attendance'].sudo().with_context(
            skip_face_attendance_validity=True
        ).create(vals)

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
        employee_details = []
        for employee in employees.filtered('image_1920'):
            shift_data = employee._get_face_attendance_shift_data()
            employee_details.append({
                "employee_id": employee.id,
                "attendance_state": shift_data['attendance_state'],
                "shift_expired": shift_data['shift_expired'],
                "shift_seconds_remaining": shift_data['shift_seconds_remaining'],
                "image": employee.image_1920,
            })
        return employee_details

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

        shift_data = employee._get_face_attendance_shift_data()
        if (
            attendance_action == 'check_out'
            and shift_data['attendance_state'] != 'checked_in'
        ):
            return {
                'error': 'already_checked_out',
                'attendance_state': shift_data['attendance_state'],
                'shift_expired': shift_data['shift_expired'],
            }

        geo_information = BaseHrAttendance._get_geoip_response(
            'kiosk',
            latitude=latitude,
            longitude=longitude,
            device_tracking_enabled=company.attendance_device_tracking,
        )
        if attendance_action == 'check_in':
            action_date = fields.Datetime.now()
            employee._close_open_face_attendance(action_date, geo_information)
            self._create_face_check_in(employee, action_date, geo_information)
        else:
            employee._attendance_action_change(geo_information)
        employee.invalidate_recordset()
        return BaseHrAttendance._get_employee_info_response(employee)
