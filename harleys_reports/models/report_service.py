from odoo import api, models
from odoo.exceptions import AccessError

from .reports import get_report
from .reports.cost_comparison import compute_comparison, list_products_for_template, list_warehouses
from .reports.dynamic import DynamicModelReport, list_dynamic_models
from .reports.registry import REPORTS


class HarleysReportsService(models.AbstractModel):
    _name = "harleys.reports.service"
    _description = "Harleys Reports Service"

    @api.model
    def _check_reports_access(self):
        if not self.env.user.has_group("harleys_reports.group_harleys_reports"):
            raise AccessError("You are not allowed to access Harleys Reports.")

    @api.model
    def _get_provider(self, report_key):
        self._check_reports_access()
        return get_report(report_key)(self.env)

    @api.model
    @api.readonly
    def get_current_user_info(self):
        self._check_reports_access()
        user = self.env.user
        employee = user.employee_id if "employee_id" in user._fields else self.env["hr.employee"]
        return {
            "name": user.name,
            "login": user.login,
            "employee_code": employee.barcode if employee else False,
        }

    @api.model
    @api.readonly
    def get_reports(self):
        self._check_reports_access()
        reports = []
        for report_key in sorted(REPORTS.keys()):
            provider = get_report(report_key)(self.env)
            provider.check_source_access()
            reports.append(provider.summary())
        return reports

    @api.model
    @api.readonly
    def get_report_metadata(self, report_key):
        provider = self._get_provider(report_key)
        provider.check_source_access()
        return provider.metadata()

    @api.model
    @api.readonly
    def get_report_page(self, report_key, filters=None, offset=0, limit=80, sort=None):
        provider = self._get_provider(report_key)
        return provider.get_page(filters or {}, offset, limit, sort or {})

    @api.model
    @api.readonly
    def search_filter_options(self, report_key, filter_key, term="", limit=20):
        provider = self._get_provider(report_key)
        return provider.search_filter_options(filter_key, term, limit)

    @api.model
    def _get_dynamic_provider(self, model_name):
        self._check_reports_access()
        return DynamicModelReport(self.env, model_name)

    @api.model
    @api.readonly
    def get_dynamic_models(self):
        self._check_reports_access()
        return list_dynamic_models(self.env)

    @api.model
    @api.readonly
    def get_dynamic_model_metadata(self, model_name):
        return self._get_dynamic_provider(model_name).metadata()

    @api.model
    @api.readonly
    def get_dynamic_report_page(self, model_name, columns, filters=None, offset=0, limit=20, sort=None):
        provider = self._get_dynamic_provider(model_name)
        return provider.get_page(columns, filters or {}, offset, limit, sort or {})

    @api.model
    @api.readonly
    def search_dynamic_filter_options(self, model_name, field_name, term="", limit=20):
        provider = self._get_dynamic_provider(model_name)
        return provider.search_filter_options(field_name, term, limit)

    @api.model
    @api.readonly
    def get_cost_comparison_warehouses(self):
        self._check_reports_access()
        return list_warehouses(self.env)

    @api.model
    @api.readonly
    def compute_cost_comparison(self, csv_content, warehouse_codes):
        self._check_reports_access()
        return compute_comparison(self.env, csv_content, warehouse_codes)

    @api.model
    @api.readonly
    def get_cost_comparison_template_products(self):
        self._check_reports_access()
        return list_products_for_template(self.env)
