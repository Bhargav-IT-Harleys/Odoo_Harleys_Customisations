from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    b2b_default_vendor_account_id = fields.Many2one(
        "vendor.account",
        string="Default Vendor Account",
        config_parameter="b2b_erp_integration.default_vendor_account_id",
    )
