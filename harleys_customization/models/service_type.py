from odoo import api, fields, models, _


PRIORITY = [
    ('0', 'Low priority'),
    ('1', 'Medium priority'),
    ('2', 'High priority'),
    ('3', 'Urgent'),
]

class ServiceType(models.Model):
    _name = 'service.type'
    _description = 'Service Type'

    name = fields.Char(string="Service", required=True)
    priority = fields.Selection(PRIORITY, string='Priority', default='0', required=True)
