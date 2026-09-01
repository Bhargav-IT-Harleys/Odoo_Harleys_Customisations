from collections import defaultdict
from datetime import timedelta
from odoo import fields
from odoo.exceptions import ValidationError
from .base import PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin
from .date_utils import date_boundary, to_local_string
from .registry import register_report

_DEFAULT_WINDOW_DAYS = 15

@register_report
class PhysicalInventoryReport(SqlRowsReportMixin, ReportProvider):
    key = "physical_inventory"
    title = "Physical Inventory"
    description = (
        "Every physical-count correction ever applied - what the system's book quantity was "
        "right before each count, what was actually counted, and who did it."
    )
    model_name = "stock.move.line"

    filters = (
        {"key": "date_from", "label": "Date From", "type": "date", "group": "primary"},
        {"key": "date_to", "label": "Date To", "type": "date", "group": "primary"},
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        PRODUCT_SEARCH_FILTER,
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
    )
    columns = (
        {"key": "date", "label": "Date", "type": "datetime", "sortable": True},
        {"key": "warehouse", "label": "Warehouse", "type": "text", "sortable": True, "optional": True},
        {"key": "location", "label": "Location", "type": "text", "sortable": True},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True, "optional": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True},
        {"key": "lot", "label": "Lot", "type": "text", "sortable": True},
        {"key": "uom", "label": "UOM", "type": "text", "sortable": True},
        {"key": "system_qty", "label": "Sys Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "counted_qty", "label": "Counted Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "adjustment_qty", "label": "Adj Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "unit_cost", "label": "Unit Cost", "type": "float", "sortable": True, "align": "end"},
        {"key": "total_cost", "label": "Total Cost", "type": "float", "sortable": True, "align": "end"},
        {"key": "applied_by", "label": "Applied By", "type": "text", "sortable": True, "optional": True},
        {"key": "reference", "label": "Ref", "type": "text", "sortable": True},
    )
    relation_filters = PRODUCT_RELATION_FILTERS
    # Wider than every other report's Raw Material/Packaging Materials default - physical counts
    # here are expected to cover finished/semi-finished stock too, not just incoming materials.
    default_category_names = (
        "FINISHED GOODS", "Food", "PACKAGING MATERIALS", "RAWMATERIAL",
        "Returnable Containers", "SEMI FINISHED GOODS", "SEMI FINISHED GOODS/ BROWNIES",
    )
    default_sort = {"key": "date", "direction": "desc"}
    export_row_limit_hint = "date range or warehouse selection"
    sort_fields = {
        "date": "date", "warehouse": "warehouse", "location": "location", "sku": "sku",
        "product": "product", "category": "category", "lot": "lot", "uom": "uom",
        "system_qty": "system_qty", "counted_qty": "counted_qty", "adjustment_qty": "adjustment_qty",
        "unit_cost": "unit_cost", "total_cost": "total_cost",
        "applied_by": "applied_by", "reference": "reference",
    }

    def metadata(self):
        today = fields.Date.context_today(self.model)
        default_filters = {
            "date_from": fields.Date.to_string(today - timedelta(days=_DEFAULT_WINDOW_DAYS)),
            "date_to": fields.Date.to_string(today),
            **self._default_category_filter(),
        }
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": default_filters,
            "default_sort": self.default_sort,
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
            "export_formats": ["csv", "xlsx"],
            "grouped": True,
        }

    def _normalize_filters(self, values):
        if not isinstance(values, dict):
            raise ValidationError("Invalid report filters.")
        allowed = {item["key"] for item in self.filters}
        if set(values) - allowed:
            raise ValidationError("Unsupported report filter.")
        if not values.get("date_from") or not values.get("date_to"):
            raise ValidationError("Select a date range.")
        normalized = {"date_from": values["date_from"], "date_to": values["date_to"]}
        warehouse_ids = values.get("warehouse_ids")
        if warehouse_ids:
            normalized["warehouse_ids"] = self._validate_id_list(warehouse_ids, "warehouse")
        category_ids = values.get("category_ids")
        if category_ids:
            normalized["category_ids"] = self._validate_id_list(category_ids, "category")
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        return normalized

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        warehouses = self._resolve_warehouses(values.get("warehouse_ids"))
        if not warehouses:
            return []
        category_ids = values.get("category_ids")
        search_term = values.get("search")
        date_from = date_boundary(self.env, values["date_from"])
        date_to = date_boundary(self.env, values["date_to"], end=True)

        location_to_warehouse = {}
        all_location_ids = []
        for warehouse in warehouses:
            for location_id in self._warehouse_location_ids(warehouse):
                location_to_warehouse[location_id] = warehouse
                all_location_ids.append(location_id)
        if not all_location_ids:
            return []
        self.env.cr.execute("""
            WITH move_legs AS (
                SELECT sml.id, sml.product_id, sml.location_dest_id AS location_id,
                       COALESCE(sml.lot_id, 0) AS lot_key, sml.quantity_product_uom AS delta, sml.date
                FROM stock_move_line sml WHERE sml.state = 'done'
                UNION ALL
                SELECT sml.id, sml.product_id, sml.location_id AS location_id,
                       COALESCE(sml.lot_id, 0) AS lot_key, -sml.quantity_product_uom AS delta, sml.date
                FROM stock_move_line sml WHERE sml.state = 'done'
            ),
            running AS (
                SELECT id, product_id, location_id, lot_key, delta, date,
                       SUM(delta) OVER (PARTITION BY product_id, location_id, lot_key ORDER BY date, id
                                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_balance
                FROM move_legs
            ),
            inventory_adjustments AS (
                SELECT sml.id AS inventory_line_id, sml.date AS adjustment_date, sml.product_id, sml.lot_id,
                       COALESCE(sml.lot_id, 0) AS lot_key,
                       CASE WHEN src.usage = 'inventory' THEN sml.location_dest_id ELSE sml.location_id END AS location_id,
                       CASE WHEN src.usage = 'inventory' THEN sml.quantity_product_uom ELSE -sml.quantity_product_uom END AS adjustment_qty,
                       sm.create_uid AS user_id, sm.reference, sm.inventory_name
                FROM stock_move_line sml
                JOIN stock_move sm ON sm.id = sml.move_id
                JOIN stock_location src ON src.id = sml.location_id
                JOIN stock_location dest ON dest.id = sml.location_dest_id
                WHERE sm.is_inventory = TRUE AND sml.state = 'done'
                  AND (src.usage = 'inventory' OR dest.usage = 'inventory')
                  AND sml.date >= %(date_from)s AND sml.date < %(date_to)s
                  AND (sml.location_id = ANY(%(locs)s) OR sml.location_dest_id = ANY(%(locs)s))
            )
            SELECT ia.inventory_line_id, ia.adjustment_date, ia.product_id, ia.location_id, ia.lot_id,
                   ia.adjustment_qty, (r.running_balance - r.delta) AS system_qty,
                   ia.user_id, ia.reference, ia.inventory_name
            FROM inventory_adjustments ia
            JOIN running r ON r.id = ia.inventory_line_id AND r.location_id = ia.location_id
                           AND r.lot_key = ia.lot_key
        """, {"date_from": date_from, "date_to": date_to, "locs": all_location_ids})
        event_rows = self.env.cr.fetchall()
        if not event_rows:
            return []

        product_ids = list({row[2] for row in event_rows})
        allowed_product_ids = self._filter_product_ids(product_ids, category_ids, search_term)
        if not allowed_product_ids:
            return []

        all_user_ids = {row[7] for row in event_rows if row[7]}
        user_names = {user.id: user.name for user in self.env["res.users"].browse(all_user_ids)}
        location_names = {
            location.id: location.complete_name
            for location in self.env["stock.location"].browse({row[3] for row in event_rows})
        }
        lot_names = {
            lot.id: lot.name
            for lot in self.env["stock.lot"].browse({row[4] for row in event_rows if row[4]})
        }
        product_data_by_company = {}
        rows = []
        for (inventory_line_id, adjustment_date, product_id, location_id, lot_id,
             adjustment_qty, system_qty, user_id, reference, inventory_name) in event_rows:
            if product_id not in allowed_product_ids:
                continue
            warehouse = location_to_warehouse.get(location_id)
            if not warehouse:
                continue
            company_id = warehouse.company_id.id
            product = self._company_scoped_products(
                product_data_by_company, company_id, list(allowed_product_ids), ("standard_price",)
            ).get(product_id)
            if not product:
                continue
            cost = product.get("standard_price") or 0.0
            rows.append({
                "id": inventory_line_id,
                "date": to_local_string(self.env, adjustment_date),
                "warehouse": warehouse.name,
                "location": location_names.get(location_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._leaf_category(product),
                "lot": lot_names.get(lot_id, ""),
                "uom": self._display(product.get("uom_id")),
                "system_qty": round(system_qty, 2),
                "counted_qty": round(system_qty + adjustment_qty, 2),
                "adjustment_qty": round(adjustment_qty, 2),
                "unit_cost": round(cost, 2),
                "total_cost": round(adjustment_qty * cost, 2),
                "applied_by": user_names.get(user_id, ""),
                "reference": inventory_name or reference or "",
            })
        return rows

    def _group_rows(self, rows):
        by_location = defaultdict(lambda: defaultdict(list))
        for row in rows:
            by_location[row["location"]][row["date"][:10]].append(row)
        groups = []
        for location_key in sorted(by_location):
            date_map = by_location[location_key]
            date_groups = []
            loc_count = 0
            loc_adjustment = 0.0
            loc_cost = 0.0
            for date_key in sorted(date_map, reverse=True):
                date_rows = date_map[date_key]
                adjustment_total = sum(row["adjustment_qty"] for row in date_rows)
                cost_total = sum(row["total_cost"] for row in date_rows)
                date_groups.append({
                    "key": date_key,
                    "count": len(date_rows),
                    "adjustment_total": round(adjustment_total, 2),
                    "total_cost": round(cost_total, 2),
                    "rows": date_rows,
                })
                loc_count += len(date_rows)
                loc_adjustment += adjustment_total
                loc_cost += cost_total
            groups.append({
                "key": location_key,
                "count": loc_count,
                "adjustment_total": round(loc_adjustment, 2),
                "total_cost": round(loc_cost, 2),
                "groups": date_groups,
            })
        return groups

    def get_grouped_rows(self, filters, sort):
        self.check_source_access()
        rows = self._sort_rows(self._build_rows(filters), sort)
        if len(rows) > self.maximum_export_rows:
            raise ValidationError(
                f"This view exceeds the {self.maximum_export_rows:,} row limit. "
                "Narrow the date range or warehouse selection and try again."
            )
        return {"groups": self._group_rows(rows), "total": len(rows)}
