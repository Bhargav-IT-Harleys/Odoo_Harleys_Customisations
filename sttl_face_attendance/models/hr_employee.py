# -*- coding: utf-8 -*-

from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = 'hr.employee'

    face_descriptor = fields.Text(
        string='Face Descriptor',
        copy=False,
        help='Stored face recognition descriptor generated when the employee face image is captured.',
    )

    def new_employee_image(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'new_employee_image',
            'params': {
                'employee_id': self.id,
            }
        }

    def register_face(self, image_data, face_descriptor=None):
        try:
            if image_data.startswith('data:image/png;base64,'):
                image_data = image_data.split('base64,')[1]

            if image_data:
                self.image_1920 = image_data
                self.face_descriptor = face_descriptor
                _logger.info("Image saved successfully.")
            else:
                _logger.warning("No image data provided.")
        except Exception as e:
            _logger.error("Error registering face: %s", str(e))
