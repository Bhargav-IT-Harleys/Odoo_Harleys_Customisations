from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import HarleysReportsCase


@tagged("post_install", "-at_install")
class TestMoveHistory(HarleysReportsCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["harleys.reports.service"].with_user(self.user)

    def test_metadata_is_allow_listed(self):
        metadata = self.service.get_report_metadata("move_history")
        self.assertEqual(metadata["key"], "move_history")
        self.assertEqual(metadata["default_filters"], {"state": "done"})
        self.assertNotIn("model", metadata)
        self.assertNotIn("domain", metadata)

    def test_page_filters_sort_and_pagination(self):
        page = self.service.get_report_page(
            "move_history",
            {"product_id": self.product.id, "location_id": self.source.id},
            0,
            40,
            {"key": "date", "direction": "desc"},
        )
        self.assertTrue(any(row["id"] == self.move_line.id for row in page["rows"]))
        self.assertLessEqual(len(page["rows"]), 40)

    def test_empty_result(self):
        page = self.service.get_report_page(
            "move_history", {"reference": "does-not-exist"}, 0, 40, {}
        )
        self.assertEqual(page["rows"], [])
        self.assertEqual(page["total"], 0)

    def test_arbitrary_inputs_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.get_report_page("res_users", {}, 0, 40, {})
        with self.assertRaises(ValidationError):
            self.service.get_report_page("move_history", {"domain": []}, 0, 40, {})
        with self.assertRaises(ValidationError):
            self.service.get_report_page("move_history", {}, 0, 40, {"key": "password", "direction": "asc"})
        with self.assertRaises(ValidationError):
            self.service.get_report_page("move_history", {}, 0, 10000, {})

    def test_filter_option_search(self):
        options = self.service.search_filter_options(
            "move_history", "product_id", "Reports Test", 20
        )
        self.assertIn(self.product.id, [option["id"] for option in options])

    def test_export_uses_provider_rows(self):
        provider = self.service._get_provider("move_history")
        rows = provider.export_rows({"product_id": self.product.id}, {"key": "date", "direction": "desc"})
        self.assertTrue(any(row["id"] == self.move_line.id for row in rows))

    def test_reports_list_includes_accessible_modules(self):
        reports = self.service.get_reports()
        keys = {report["key"] for report in reports}
        self.assertIn("move_history", keys)
        self.assertIn("internal_transfers", keys)

    def test_export_selected_rows_uses_row_ids(self):
        provider = self.service._get_provider("move_history")
        rows = provider.export_rows({}, {"key": "date", "direction": "desc"}, row_ids=[self.move_line.id])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], self.move_line.id)
