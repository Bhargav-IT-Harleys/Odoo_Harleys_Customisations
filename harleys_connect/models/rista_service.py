from types import SimpleNamespace

from odoo import api, models
from odoo.exceptions import AccessError

from ..services.adapters.rista.client import RistaReportService
from ..services.adapters.rista.constants import REPORT_CATALOG, RistaConstants

RISTA_DEFAULT_BASE_URL = RistaConstants.DEFAULT_BASE_URL


class HarleysConnectRistaService(models.AbstractModel):
    """Backend for the Rista Reports client action - fetches live from the Rista
    API on every call and returns display-ready rows. Deliberately stateless: no
    model backs this (AbstractModel creates no table), so there's nothing to
    persist or migrate while the connector schema (connect.raw.record and
    friends, see HANDOFF_harleys_connect.md) is still being decided."""

    _name = "harleys_connect.rista.service"
    _description = "Harley's Connect - Rista Reports Service"

    @api.model
    def _check_access(self):
        if not self.env.user.has_group("harleys_connect.group_connect_user"):
            raise AccessError("You are not allowed to access Harley's Connect.")

    @api.model
    def _get_rista_config(self):
        params = self.env["ir.config_parameter"].sudo()
        return SimpleNamespace(
            base_url=params.get_param("harleys_connect.rista_base_url") or RISTA_DEFAULT_BASE_URL,
            api_key=params.get_param("harleys_connect.rista_api_key"),
            secret_key=params.get_param("harleys_connect.rista_secret_key"),
        )

    @api.model
    @api.readonly
    def get_rista_catalog(self):
        self._check_access()
        return [
            {key: value for key, value in report.items() if key != "field_mapping"}
            for report in REPORT_CATALOG
        ]

    @api.model
    @api.readonly
    def get_rista_report(self, report_id, params=None):
        self._check_access()
        config = self._get_rista_config()
        return RistaReportService.fetch_report(config, report_id, params or {})
