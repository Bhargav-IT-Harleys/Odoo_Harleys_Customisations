from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    harleys_parent_mo_lead_time = fields.Integer(
        string="Harley's Parent MO Lead Time",
        config_parameter='harleys_customization.parent_mo_lead_time',
    )
