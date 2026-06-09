# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    face_attendance_shift_hours = fields.Float(
        string="Face Attendance Shift Duration",
        config_parameter='sttl_face_attendance.shift_hours',
        default=12.0,
        help="After this many hours, face attendance allows a new check-in "
             "while the previous attendance is still open.",
    )

    @api.constrains('face_attendance_shift_hours')
    def _check_face_attendance_shift_hours(self):
        for settings in self:
            if settings.face_attendance_shift_hours <= 0:
                raise ValidationError(
                    _("Face Attendance Shift Duration must be greater than zero.")
                )
