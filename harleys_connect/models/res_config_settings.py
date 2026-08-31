from odoo import fields, models

from .rista_service import RISTA_DEFAULT_BASE_URL


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    harleys_connect_default_vendor_account_id = fields.Many2one(
        "vendor.account",
        string="Default Vendor Account",
        config_parameter="harleys_connect.default_vendor_account_id",
    )

    # Rista is a reporting-only connector (no push/orders), so unlike Hyperpure it has
    # no vendor.account record - its credentials live directly in ir.config_parameter
    # until the wider connector schema (see HANDOFF_harleys_connect.md) is finalised.
    rista_base_url = fields.Char(
        string="Rista Base URL",
        config_parameter="harleys_connect.rista_base_url",
        default=RISTA_DEFAULT_BASE_URL,
    )
    rista_api_key = fields.Char(
        string="Rista API Key",
        config_parameter="harleys_connect.rista_api_key",
        groups="harleys_connect.group_connect_manager",
    )
    rista_secret_key = fields.Char(
        string="Rista Secret Key",
        config_parameter="harleys_connect.rista_secret_key",
        groups="harleys_connect.group_connect_manager",
    )
