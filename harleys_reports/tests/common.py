from odoo import Command
from odoo.tests.common import TransactionCase


class HarleysReportsCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reports_group = cls.env.ref("harleys_reports.group_harleys_reports")
        cls.stock_group = cls.env.ref("stock.group_stock_user")
        cls.user = cls.env["res.users"].create({
            "name": "Reports User",
            "login": "reports-user",
            "email": "reports@example.com",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
            "group_ids": [Command.set((cls.reports_group | cls.stock_group).ids)],
        })
        cls.no_reports_user = cls.env["res.users"].create({
            "name": "Stock Only User",
            "login": "stock-only-user",
            "email": "stock-only@example.com",
            "company_id": cls.env.company.id,
            "company_ids": [Command.set(cls.env.company.ids)],
            "group_ids": [Command.set(cls.stock_group.ids)],
        })
        cls.product = cls.env["product.product"].create({
            "name": "Reports Test Product",
            "is_storable": True,
        })
        cls.source = cls.env["stock.location"].create({
            "name": "Reports Source",
            "usage": "internal",
            "company_id": cls.env.company.id,
        })
        cls.destination = cls.env["stock.location"].create({
            "name": "Reports Destination",
            "usage": "internal",
            "company_id": cls.env.company.id,
        })
        cls.move = cls.env["stock.move"].create({
            "description_picking": "REPORTS/TEST/001",
            "product_id": cls.product.id,
            "product_uom_qty": 3,
            "product_uom": cls.product.uom_id.id,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
        })
        cls.move_line = cls.env["stock.move.line"].create({
            "move_id": cls.move.id,
            "product_id": cls.product.id,
            "product_uom_id": cls.product.uom_id.id,
            "quantity": 3,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
        })
