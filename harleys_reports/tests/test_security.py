from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import HarleysReportsCase


@tagged("post_install", "-at_install")
class TestReportsSecurity(HarleysReportsCase):
    def test_non_member_cannot_call_service(self):
        service = self.env["harleys.reports.service"].with_user(self.no_reports_user)
        with self.assertRaises(AccessError):
            service.get_reports()
        with self.assertRaises(AccessError):
            service.get_report_page("move_history", {}, 0, 40, {})

    def test_menu_is_group_restricted(self):
        menu = self.env.ref("harleys_reports.menu_harleys_reports_root")
        self.assertIn(self.reports_group, menu.group_ids)

    def test_reports_group_does_not_remove_stock_write_access(self):
        move = self.move.with_user(self.user)
        self.assertTrue(move.has_access("write"))
        move.write({"description_picking": "REPORTS/TEST/UPDATED"})
        self.assertEqual(move.description_picking, "REPORTS/TEST/UPDATED")
