import io
import zipfile

from odoo.tests import tagged

from odoo.addons.harleys_reports.controllers.export import HarleysReportsExport

from .common import HarleysReportsCase


@tagged("post_install", "-at_install")
class TestReportExport(HarleysReportsCase):
    def setUp(self):
        super().setUp()
        self.controller = HarleysReportsExport()
        self.columns = ({"key": "reference", "label": "Reference", "type": "text"},)

    def test_csv_export_and_formula_protection(self):
        content = self.controller._csv(self.columns, [{"reference": "=unsafe"}]).decode("utf-8-sig")
        self.assertIn("Reference", content)
        self.assertIn("'=unsafe", content)

    def test_xlsx_export(self):
        content = self.controller._xlsx(self.columns, [{"reference": "REPORTS/TEST"}])
        self.assertTrue(zipfile.is_zipfile(io.BytesIO(content)))
