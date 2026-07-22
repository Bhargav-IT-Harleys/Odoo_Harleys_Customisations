from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hp_default_configuration = fields.Many2one(
        "hp.configuration",
        string="Default Vendor Configuration",
        config_parameter="hp.default_configuration",
    )