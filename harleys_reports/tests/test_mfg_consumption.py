from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import HarleysReportsCase


@tagged("post_install", "-at_install")
class TestMfgConsumption(HarleysReportsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["harleys.reports.service"].with_user(cls.user)

        cls.section = cls.env["production.section"].create({"name": "Bakery", "code": "BAK"})
        cls.other_section = cls.env["production.section"].create({"name": "Confectionery", "code": "CONF"})

        cls.fg_category = cls.env["product.category"].create({"name": "Test FG Category"})

        cls.flour = cls.env["product.product"].create({"name": "Flour", "default_code": "MAT-FLOUR"})
        cls.oil = cls.env["product.product"].create({"name": "Oil"})
        cls.sugar = cls.env["product.product"].create({"name": "Sugar"})
        cls.sugar.write({"standard_price": 50.0})
        cls.mystery_ingredient = cls.env["product.product"].create({"name": "Mystery Ingredient"})
        cls.semi_finished = cls.env["product.product"].create({"name": "Semi Finished X", "is_storable": True})
        cls.finished = cls.env["product.product"].create({
            "name": "Product A", "is_storable": True, "default_code": "FG-A",
        })
        cls.finished.write({"section": cls.section.id, "categ_id": cls.fg_category.id})
        cls.finished_b = cls.env["product.product"].create({"name": "Product B", "is_storable": True})
        cls.finished_b.write({"section": cls.other_section.id})

        # Semi Finished X = 0.03 Flour + 0.01 Oil (per 1 unit). Left inactive deliberately -
        # this module forces new BoMs inactive until approved, and the provider must still find
        # it (see _resolve_child_boms).
        cls.child_bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.semi_finished.product_tmpl_id.id,
            "product_id": cls.semi_finished.id,
            "product_qty": 1.0,
            "product_uom_id": cls.semi_finished.uom_id.id,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.flour.id, "product_qty": 0.03, "product_uom_id": cls.flour.uom_id.id}),
                (0, 0, {"product_id": cls.oil.id, "product_qty": 0.01, "product_uom_id": cls.oil.uom_id.id}),
            ],
        })
        # Product A = 2 Semi Finished X + 0.05 Sugar (per 1 unit).
        cls.parent_bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.finished.product_tmpl_id.id,
            "product_id": cls.finished.id,
            "product_qty": 1.0,
            "product_uom_id": cls.finished.uom_id.id,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.semi_finished.id, "product_qty": 2.0,
                        "product_uom_id": cls.semi_finished.uom_id.id}),
                (0, 0, {"product_id": cls.sugar.id, "product_qty": 0.05, "product_uom_id": cls.sugar.uom_id.id}),
            ],
        })
        # Product B = 0.02 Sugar directly (per 1 unit) - shares the Sugar material with Product A
        # so the per-product row separation can be exercised.
        cls.parent_bom_b = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.finished_b.product_tmpl_id.id,
            "product_id": cls.finished_b.id,
            "product_qty": 1.0,
            "product_uom_id": cls.finished_b.uom_id.id,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.sugar.id, "product_qty": 0.02, "product_uom_id": cls.sugar.uom_id.id}),
            ],
        })

        cls.window_start = fields.Datetime.now() - timedelta(days=1)

        cls.mo = cls._make_done_mo(cls.finished, cls.parent_bom, qty_produced=1.0)
        cls.mo_b = cls._make_done_mo(cls.finished_b, cls.parent_bom_b, qty_produced=1.0)

        # Flattened requirement for 1 unit of Product A: Flour 0.06, Oil 0.02, Sugar 0.05.
        cls._make_consumption_move(cls.mo, cls.flour, 0.06)
        cls._make_consumption_move(cls.mo, cls.oil, 0.03)
        cls._make_consumption_move(cls.mo, cls.sugar, 0.04)
        cls._make_consumption_move(cls.mo, cls.mystery_ingredient, 5.0)
        cls._make_scrap(cls.mo, cls.oil, 0.01, raw_material=True)
        # Product B's own requirement: Sugar 0.02.
        cls._make_consumption_move(cls.mo_b, cls.sugar, 0.02)

        # Child MO: origin references the parent MO's own name - must be excluded by the
        # "/MO/" filter even though its dates/state/section otherwise match, and even though
        # its (deliberately oversized) consumption would badly skew the results if included.
        cls.child_mo = cls._make_done_mo(cls.finished, cls.parent_bom, qty_produced=1.0)
        cls.child_mo.write({"origin": cls.mo.name})
        cls._make_consumption_move(cls.child_mo, cls.flour, 100.0)

        # Dedicated fixture for finished-goods scrap inflating Required, kept isolated from the
        # Flour/Oil/Sugar numbers above so its own math is easy to verify independently.
        cls.scrap_material = cls.env["product.product"].create({"name": "Scrap Test Material"})
        cls.scrap_finished = cls.env["product.product"].create(
            {"name": "Scrap Test Product", "is_storable": True}
        )
        cls.scrap_finished.write({"section": cls.section.id})
        cls.scrap_bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.scrap_finished.product_tmpl_id.id,
            "product_id": cls.scrap_finished.id,
            "product_qty": 1.0,
            "product_uom_id": cls.scrap_finished.uom_id.id,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.scrap_material.id, "product_qty": 0.1,
                        "product_uom_id": cls.scrap_material.uom_id.id}),
            ],
        })
        # Produced 1 unit, of which 1 more unit was scrapped after production: Total = 2, so
        # Required = 0.1 * 2 = 0.2 - matching Actual exactly only because scrap is included.
        cls.scrap_mo = cls._make_done_mo(cls.scrap_finished, cls.scrap_bom, qty_produced=1.0)
        cls._make_scrap(cls.scrap_mo, cls.scrap_finished, 1.0, raw_material=False)
        cls._make_consumption_move(cls.scrap_mo, cls.scrap_material, 0.2)

        # Dedicated Production Center fixture: a second warehouse whose name contains
        # "Production", with its own manufacturing operation type, and one MO explicitly routed
        # through it (mrp.production.picking_type_id is normally auto-computed onto whatever the
        # default company warehouse resolves to, so this needs an explicit override).
        cls.production_warehouse = cls.env["stock.warehouse"].create({
            "name": "Production Line 1", "code": "PRODL1", "company_id": cls.env.company.id,
        })
        cls.production_picking_type = cls.env["stock.picking.type"].create({
            "name": "Production Line 1 Manufacturing",
            "code": "mrp_operation",
            "sequence_code": "PRODL1MO",
            "warehouse_id": cls.production_warehouse.id,
            "company_id": cls.env.company.id,
        })
        cls.center_material = cls.env["product.product"].create({"name": "Center Test Material"})
        cls.center_finished = cls.env["product.product"].create(
            {"name": "Center Test Product", "is_storable": True}
        )
        cls.center_bom = cls.env["mrp.bom"].create({
            "product_tmpl_id": cls.center_finished.product_tmpl_id.id,
            "product_id": cls.center_finished.id,
            "product_qty": 1.0,
            "product_uom_id": cls.center_finished.uom_id.id,
            "type": "normal",
            "bom_line_ids": [
                (0, 0, {"product_id": cls.center_material.id, "product_qty": 1.0,
                        "product_uom_id": cls.center_material.uom_id.id}),
            ],
        })
        cls.center_mo = cls._make_done_mo(cls.center_finished, cls.center_bom, qty_produced=1.0)
        cls.center_mo.write({"picking_type_id": cls.production_picking_type.id})
        cls._make_consumption_move(cls.center_mo, cls.center_material, 1.0)

    @classmethod
    def _make_done_mo(cls, product, bom, qty_produced):
        mo = cls.env["mrp.production"].create({
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "company_id": cls.env.company.id,
            "date_start": cls.window_start,
        })
        mo.write({"bom_id": bom.id})
        mo.write({"product_qty": qty_produced})
        move = cls.env["stock.move"].create({
            "production_id": mo.id,
            "product_id": product.id,
            "product_uom_qty": qty_produced,
            "product_uom": product.uom_id.id,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
            "state": "done",
        })
        cls.env["stock.move.line"].create({
            "move_id": move.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": qty_produced,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
        })
        # state/date_finished are stored computes on mrp.production, but the underlying moves
        # created above already satisfy _compute_state's own "all raw/finished moves done" done
        # condition, and _compute_date_finished explicitly skips once state == 'done' - so this
        # explicit write is both correct and safe from being silently discarded.
        mo.write({"state": "done", "date_finished": cls.window_start + timedelta(hours=1)})
        return mo

    @classmethod
    def _make_consumption_move(cls, mo, product, qty):
        move = cls.env["stock.move"].create({
            "raw_material_production_id": mo.id,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
            "state": "done",
        })
        cls.env["stock.move.line"].create({
            "move_id": move.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": qty,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
        })
        return move

    @classmethod
    def _make_scrap(cls, mo, product, qty, raw_material):
        scrap = cls.env["stock.scrap"].create({
            "production_id": mo.id,
            "product_id": product.id,
            "scrap_qty": qty,
            "product_uom_id": product.uom_id.id,
            "location_id": cls.source.id,
            "company_id": cls.env.company.id,
            "state": "done",
        })
        scrap_move_vals = {
            "scrap_id": scrap.id,
            "product_id": product.id,
            "product_uom_qty": qty,
            "product_uom": product.uom_id.id,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
            "state": "done",
        }
        scrap_move_vals["raw_material_production_id" if raw_material else "production_id"] = mo.id
        scrap_move = cls.env["stock.move"].create(scrap_move_vals)
        # stock.scrap.scrap_qty is itself a stored compute that re-derives from
        # move_ids[0].quantity once the move exists - without a move_line here that quantity
        # stays 0, silently zeroing out the scrap_qty set above.
        cls.env["stock.move.line"].create({
            "move_id": scrap_move.id,
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": qty,
            "location_id": cls.source.id,
            "location_dest_id": cls.destination.id,
            "company_id": cls.env.company.id,
        })
        return scrap

    def _rows(self, extra_filters=None):
        filters = {"date_from": "2000-01-01", "date_to": "2999-01-01"}
        filters.update(extra_filters or {})
        page = self.service.get_report_page("mfg_consumption", filters, 0, 200, {})
        return page["rows"]

    def _row(self, rows, component_name, product_name=None):
        matches = [
            row for row in rows
            if row["component"] == component_name and (product_name is None or row["product_name"] == product_name)
        ]
        self.assertEqual(
            len(matches), 1,
            f"expected exactly one {component_name}/{product_name} row, found {matches}",
        )
        return matches[0]

    def test_nested_bom_flattened_and_matched(self):
        flour = self._row(self._rows(), "Flour")
        self.assertAlmostEqual(flour["required"], 0.06, places=4)
        self.assertAlmostEqual(flour["actual"], 0.06, places=4)
        self.assertEqual(flour["status"], "match")
        self.assertEqual(flour["product_name"], "Product A")
        self.assertEqual(flour["material_uom"], self.flour.uom_id.name)

    def test_over_consumption_includes_raw_material_scrap(self):
        oil = self._row(self._rows(), "Oil")
        self.assertAlmostEqual(oil["required"], 0.02, places=4)
        self.assertAlmostEqual(oil["actual"], 0.04, places=4)  # 0.03 consumed + 0.01 scrap
        self.assertAlmostEqual(oil["scrap"], 0.01, places=4)
        self.assertEqual(oil["status"], "over")

    def test_scrap_column_is_zero_without_scrap(self):
        # Flour has ordinary consumption only (no scrap fixture) - the optional Scrap column
        # should read 0, not be missing or leak Oil's scrap onto an unrelated material.
        flour = self._row(self._rows(), "Flour")
        self.assertEqual(flour["scrap"], 0.0)

    def test_unexpected_consumption_is_shown(self):
        mystery = self._row(self._rows(), "Mystery Ingredient")
        self.assertEqual(mystery["required"], 0.0)
        self.assertAlmostEqual(mystery["actual"], 5.0, places=4)
        self.assertEqual(mystery["status"], "unexpected")

    def test_child_mo_excluded_by_origin_filter(self):
        flour = self._row(self._rows(), "Flour")
        self.assertAlmostEqual(flour["actual"], 0.06, places=4)  # not 100.06

    def test_same_material_shown_separately_per_product(self):
        # Sugar is required by both Product A and Product B - the row grain is now
        # (Production Center, Product, Material), so it must appear as two distinct rows
        # rather than being aggregated into one, unlike the previous Material-only design.
        rows = self._rows()
        sugar_rows = [row for row in rows if row["component"] == "Sugar"]
        self.assertEqual(len(sugar_rows), 2)

        sugar_a = self._row(rows, "Sugar", product_name="Product A")
        self.assertAlmostEqual(sugar_a["required"], 0.05, places=4)
        self.assertAlmostEqual(sugar_a["actual"], 0.04, places=4)

        sugar_b = self._row(rows, "Sugar", product_name="Product B")
        self.assertAlmostEqual(sugar_b["required"], 0.02, places=4)
        self.assertAlmostEqual(sugar_b["actual"], 0.02, places=4)

    def test_variance_value_uses_standard_price(self):
        sugar_a = self._row(self._rows(), "Sugar", product_name="Product A")
        self.assertAlmostEqual(sugar_a["variance"], -0.01, places=4)
        self.assertAlmostEqual(sugar_a["variance_value"], -0.5, places=4)  # -0.01 * 50.0

    def test_finished_goods_scrap_inflates_required(self):
        material = self._row(self._rows(), "Scrap Test Material")
        # mrp.production.qty_produced itself already sums the produced move (1) and the
        # finished-goods scrap move (1) since both attach to move_finished_ids for the same
        # product - Total ends up 2 without the provider adding scrap separately. Required =
        # 0.1 * 2 = 0.2, matching Actual exactly only because that scrap is reflected in Total.
        self.assertAlmostEqual(material["required"], 0.2, places=4)
        self.assertAlmostEqual(material["actual"], 0.2, places=4)
        self.assertEqual(material["status"], "match")

    def test_production_section_filter(self):
        rows = self._rows({"production_section_ids": [self.section.id]})
        sugar = self._row(rows, "Sugar")  # only Product A (Bakery) matches now, so unambiguous
        self.assertAlmostEqual(sugar["required"], 0.05, places=4)

        rows = self._rows({"production_section_ids": [self.other_section.id]})
        sugar = self._row(rows, "Sugar")  # only Product B (Confectionery) matches now
        self.assertAlmostEqual(sugar["required"], 0.02, places=4)

    def test_optional_columns_populated(self):
        flour = self._row(self._rows(), "Flour")
        self.assertEqual(flour["fg_internal_reference"], "FG-A")
        self.assertEqual(flour["material_internal_reference"], "MAT-FLOUR")
        self.assertEqual(flour["fg_category"], "Test FG Category")
        self.assertEqual(flour["production_section"], "Bakery")

    def test_search_filter_by_finished_product(self):
        rows = self._rows({"search": "Product A"})
        self.assertTrue(any(row["component"] == "Flour" for row in rows))
        self.assertFalse(any(row["product_name"] == "Product B" for row in rows))

        rows = self._rows({"search": "FG-A"})  # internal reference of Product A
        self.assertTrue(any(row["component"] == "Flour" for row in rows))

    def test_category_filter_by_finished_product(self):
        rows = self._rows({"category_ids": [self.fg_category.id]})
        self.assertTrue(all(row["product_name"] == "Product A" for row in rows))
        self.assertTrue(any(row["component"] == "Flour" for row in rows))

    def test_production_center_filter_and_column(self):
        rows = self._rows({"production_center_ids": [self.production_warehouse.id]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["component"], "Center Test Material")
        self.assertEqual(rows[0]["production_center"], "Production Line 1")

        # A center that exists but wasn't used by any qualifying MO returns nothing.
        other_center = self.env["stock.warehouse"].create({
            "name": "Production Line 2", "code": "PRODL2", "company_id": self.env.company.id,
        })
        rows = self._rows({"production_center_ids": [other_center.id]})
        self.assertEqual(rows, [])

    def test_production_center_options_restricted_to_production_named_warehouses(self):
        non_production_warehouse = self.env["stock.warehouse"].create({
            "name": "Central Store", "code": "CSTORE", "company_id": self.env.company.id,
        })
        options = self.service.search_filter_options("mfg_consumption", "production_center_ids", "", 50)
        option_names = {option["label"] for option in options}
        self.assertIn("Production Line 1", option_names)
        self.assertNotIn(non_production_warehouse.name, option_names)

    def test_export_selected_rows_uses_integer_row_ids(self):
        # The row id must be a plain int, not a composite string - the export controller does
        # int(row_id) on every id the client sends back for a "export selected rows" request
        # (see controllers/export.py), which would raise ValueError on anything else.
        rows = self._rows()
        flour_row = self._row(rows, "Flour")
        self.assertIsInstance(flour_row["id"], int)

        provider = self.service._get_provider("mfg_consumption")
        exported = provider.export_rows(
            {"date_from": "2000-01-01", "date_to": "2999-01-01"}, {}, row_ids=[flour_row["id"]],
        )
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["component"], "Flour")

    def test_date_range_is_required(self):
        with self.assertRaises(ValidationError):
            self.service.get_report_page("mfg_consumption", {}, 0, 40, {})
