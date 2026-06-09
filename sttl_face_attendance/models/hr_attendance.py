# -*- coding: utf-8 -*-

from odoo import api, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        if self.env.context.get('skip_face_attendance_validity'):
            return
        return super()._check_validity()
