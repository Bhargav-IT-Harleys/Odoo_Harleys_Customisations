# -*- coding: utf-8 -*-

from datetime import timedelta
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = 'hr.employee'

    def new_employee_image(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'new_employee_image',
            'params': {
                'employee_id': self.id,
            }
        }

    def register_face(self, image_data):
        try:
            if image_data.startswith('data:image/png;base64,'):
                image_data = image_data.split('base64,')[1]

            if image_data:
                self.image_1920 = image_data
                _logger.info("Image saved successfully.")
            else:
                _logger.warning("No image data provided.")
        except Exception as e:
            _logger.error("Error registering face: %s", str(e))

    def _get_face_attendance_shift_data(self):
        self.ensure_one()
        shift_hours_value = self.env['ir.config_parameter'].sudo().get_param(
            'sttl_face_attendance.shift_hours',
            default='12.0',
        )
        try:
            shift_hours = float(shift_hours_value)
        except (TypeError, ValueError):
            shift_hours = 12.0
        if shift_hours <= 0:
            shift_hours = 12.0

        open_attendance = self.env['hr.attendance'].sudo().search([
            ('employee_id', '=', self.id),
            ('check_out', '=', False),
        ], order='check_in desc', limit=1)
        shift_end = False
        shift_expired = False
        shift_seconds_remaining = 0

        if open_attendance:
            shift_end = open_attendance.check_in + timedelta(
                hours=shift_hours
            )
            shift_seconds_remaining = max(
                0,
                (shift_end - fields.Datetime.now()).total_seconds(),
            )
            shift_expired = shift_seconds_remaining == 0

        return {
            'attendance_state': 'checked_in' if open_attendance else 'checked_out',
            'shift_expired': shift_expired,
            'shift_seconds_remaining': shift_seconds_remaining,
            'shift_end': shift_end,
            'open_attendance': open_attendance,
        }

    def _close_open_face_attendance(self, action_date, geo_information=None):
        self.ensure_one()
        shift_data = self._get_face_attendance_shift_data()
        open_attendance = shift_data['open_attendance']
        if not open_attendance:
            return self.env['hr.attendance']

        check_out_date = (
            shift_data['shift_end']
            if shift_data['shift_expired']
            else action_date
        )
        vals = {'check_out': check_out_date}
        if geo_information:
            vals.update({
                'out_%s' % key: geo_information[key]
                for key in geo_information
            })
        open_attendance.sudo().with_context(
            skip_face_attendance_validity=True
        ).write(vals)
        return open_attendance
