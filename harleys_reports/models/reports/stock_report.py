from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError

from .base import PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin
from .date_utils import date_boundary
from .registry import register_report

_DEFAULT_TRAILING_DAYS = 60
_ALLOWED_TRAILING_DAYS = ("30", "60", "90")
_DEFAULT_ADU_VISIBILITY = "positive"
_ALLOWED_ADU_VISIBILITY = ("positive", "all")
_WAREHOUSE_ID_MULTIPLIER = 1_000_000


@register_report
class StockReportProvider(SqlRowsReportMixin, ReportProvider):
    key = "stock_report"
    title = "Stock Report"
    description = ""
    model_name = "stock.move.line"

    filters = (
        PRODUCT_SEARCH_FILTER,
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
        # No "no value" state here either, but unlike adu_window/adu_visibility below this one
        # legitimately allows an empty selection (see _default_reason_tag_filter) - it means
        # "exclude every scrap/Inv Adjustment move from ADU", not "show all".
        {"key": "reason_tag_ids", "label": "Inv Adj Reason", "type": "multi_relation", "group": "advanced"},
        # "required" tells the frontend not to offer a blank "All" choice for this one - unlike
        # a genuine optional filter (e.g. a Status filter elsewhere), there's no "no value" state
        # here: ADU is always computed over *some* window, and is always either visible or not.
        {"key": "adu_window", "label": "ADU Window", "type": "selection", "group": "advanced", "required": True,
         "options": [
             {"value": "30", "label": "30 Days"},
             {"value": "60", "label": "60 Days"},
             {"value": "90", "label": "90 Days"},
         ]},
        {"key": "adu_visibility", "label": "ADU Visibility", "type": "selection", "group": "advanced", "required": True,
         "options": [
             {"value": "positive", "label": "Exclude Zero/Negative ADU"},
             {"value": "all", "label": "Show All"},
         ]},
    )
    columns = (
        {"key": "warehouse", "label": "Warehouse", "type": "text", "sortable": True, "filter_key": "warehouse_ids"},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True, "filter_key": "search"},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True, "filter_key": "category_ids"},
        {"key": "uom", "label": "UoM", "type": "text", "sortable": True},
        {"key": "qoh", "label": "Quantity", "type": "float", "sortable": True, "align": "end"},
        {"key": "unit_cost", "label": "Unit Cost", "type": "float", "sortable": True, "align": "end"},
        {"key": "total_value", "label": "Stock Value", "type": "float", "sortable": True, "align": "end"},
        {"key": "avg_daily_usage", "label": "ADU", "type": "float", "sortable": True, "align": "end"},
        {"key": "days_of_supply", "label": "DOS", "type": "float", "sortable": True, "align": "end"},
        # Hidden by default - available via the Columns picker, same idea as Odoo's own
        # list-view "optional fields" toggle.
        {"key": "stock_location", "label": "Stock Location", "type": "text", "sortable": True, "optional": True},
    )
    relation_filters = {**PRODUCT_RELATION_FILTERS, "reason_tag_ids": ("stock.scrap.reason.tag", [])}
    default_category_names = ("RAWMATERIAL", "PACKAGING MATERIALS")
    # Scrap/"Inv Adjustments" (harleys_customization's relabeled stock.scrap) moves are a separate
    # mechanism from true is_inventory=TRUE corrections and aren't caught by that exclusion below -
    # every reason (Damaged, Expired, wastage, ...) was silently counting as ADU consumption until
    # this filter. Consumed/R&D are genuine usage (issued to Housekeeping/Production/R&D); the rest
    # default to excluded. See _default_reason_tag_filter.
    default_reason_tag_names = ("Consumed", "R&D")
    default_sort = {"key": "days_of_supply", "direction": "asc"}
    sort_fields = {
        "warehouse": "warehouse", "stock_location": "stock_location", "sku": "sku",
        "product": "product", "category": "category", "uom": "uom",
        "qoh": "qoh", "unit_cost": "unit_cost", "total_value": "total_value",
        "avg_daily_usage": "avg_daily_usage", "days_of_supply": "days_of_supply",
    }

    def _default_reason_tag_filter(self):
        # Unlike _default_category_filter, always emit the key (even as []) rather than omitting
        # it when nothing matches - an omitted key falls back to "select every option" on the
        # frontend, which for this filter means "count every scrap reason as consumption again",
        # exactly the bug this filter exists to fix. A missing/renamed Consumed/R&D tag should
        # fail toward "exclude all scrap", not toward reproducing the old behavior.
        ids = self._default_ids_for_names("stock.scrap.reason.tag", self.default_reason_tag_names)
        return {"reason_tag_ids": ids}

    def metadata(self):
        default_filters = {
            "adu_window": str(_DEFAULT_TRAILING_DAYS),
            "adu_visibility": _DEFAULT_ADU_VISIBILITY,
            **self._default_category_filter(),
            **self._default_reason_tag_filter(),
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
            "sidebar_note": (
                "Zero and negative ADU items are excluded by default. "
                "Switch \"ADU Visibility\" to \"Show All\" to include them. "
                "Scrapped/Inv Adjustment moves only count toward ADU when their Inv Adj Reason is "
                "selected - Consumed and R&D are selected by default; unselect all to exclude scrap "
                "entirely, or add reasons like Damaged/Expired/wastage to count those too."
            ),
        }

    def _normalize_filters(self, values):
        if not isinstance(values, dict):
            raise ValidationError("Invalid report filters.")
        allowed = {item["key"] for item in self.filters}
        if set(values) - allowed:
            raise ValidationError("Unsupported report filter.")
        normalized = {}
        for key, label in (("warehouse_ids", "warehouse"), ("category_ids", "category")):
            value = values.get(key)
            if value:
                normalized[key] = self._validate_id_list(value, label)
        # Unlike warehouse_ids/category_ids above, an explicit [] here is meaningful (see the
        # filter's own comment) and must be told apart from "key wasn't sent at all" - a request
        # that omits the key entirely (e.g. a stale API caller) falls back to the Consumed/R&D
        # default instead of silently excluding everything.
        if "reason_tag_ids" in values:
            normalized["reason_tag_ids"] = self._validate_id_list(
                values.get("reason_tag_ids") or [], "inv adj reason"
            )
        else:
            normalized["reason_tag_ids"] = self._default_reason_tag_filter()["reason_tag_ids"]
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        adu_window = values.get("adu_window")
        normalized["adu_window"] = adu_window if adu_window in _ALLOWED_TRAILING_DAYS else str(_DEFAULT_TRAILING_DAYS)
        adu_visibility = values.get("adu_visibility")
        normalized["adu_visibility"] = (
            adu_visibility if adu_visibility in _ALLOWED_ADU_VISIBILITY else _DEFAULT_ADU_VISIBILITY
        )
        return normalized

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        warehouses = self._resolve_warehouses(values.get("warehouse_ids"))
        if not warehouses:
            return []
        category_ids = values.get("category_ids")
        search_term = values.get("search")
        reason_tag_ids = values["reason_tag_ids"]
        trailing_days = int(values["adu_window"])
        adu_visibility = values["adu_visibility"]
        cutoff = date_boundary(self.env, fields.Date.context_today(self.model), end=True)
        trailing_start = cutoff - timedelta(days=trailing_days)

        location_to_warehouse = {}
        all_location_ids = []
        for warehouse in warehouses:
            for location_id in self._warehouse_location_ids(warehouse):
                location_to_warehouse[location_id] = warehouse
                all_location_ids.append(location_id)
        if not all_location_ids:
            return []

        # Presence-first, matching Raj's spec: only locations that actually hold stock right now,
        # not the full product catalog padded with zeros. One flat query across every selected
        # warehouse's locations at once - fast even with everything selected (no per-warehouse
        # catalog listing to multiply out).
        self.env.cr.execute("""
            SELECT location_id, product_id, SUM(quantity) AS qty
            FROM stock_quant
            WHERE location_id = ANY(%(locs)s)
            GROUP BY location_id, product_id
            HAVING SUM(quantity) <> 0
        """, {"locs": all_location_ids})
        quant_rows = self.env.cr.fetchall()
        if not quant_rows:
            return []

        product_ids = list({product_id for _location_id, product_id, _qty in quant_rows})
        if category_ids:
            product_ids = self.env["product.product"].search([
                ("id", "in", product_ids), ("categ_id", "child_of", category_ids),
            ]).ids
        if search_term:
            product_ids = self.env["product.product"].search([
                ("id", "in", product_ids),
                "|", ("display_name", "ilike", search_term), ("default_code", "ilike", search_term),
            ]).ids
        allowed_product_ids = set(product_ids)
        if not allowed_product_ids:
            return []

        location_names = {
            location.id: location.complete_name
            for location in self.env["stock.location"].browse({location_id for location_id, _p, _q in quant_rows})
        }

        # ADU/DOS outflow stays scoped to each warehouse's OWN locations, not the combined set
        # above - it must still count a transfer from warehouse A to warehouse B as outflow for A
        # even when both are selected, which a merged location set would wrongly stop detecting.
        outflow_by_warehouse_product = {}
        for warehouse in warehouses:
            loc_ids = self._warehouse_location_ids(warehouse)
            if not loc_ids:
                continue
            # Scrap/"Inv Adjustments" moves (harleys_customization's relabeled stock.scrap) are a
            # separate mechanism from is_inventory=TRUE corrections above - they pass every other
            # exclusion here regardless of reason, so a plain move (scrap_id IS NULL) counts as
            # before, but a scrap-linked move only counts if it carries a selected reason tag. An
            # empty reason_tag_ids therefore excludes every scrap move, not "no filter" - the
            # explicit ::int[] cast avoids relying on Postgres to infer a type for an empty array.
            self.env.cr.execute("""
                SELECT sml.product_id, COALESCE(SUM(sml.quantity), 0) AS outflow
                FROM stock_move_line sml
                JOIN stock_move sm ON sm.id = sml.move_id
                LEFT JOIN stock_location dest_loc ON dest_loc.id = sml.location_dest_id
                WHERE sml.state = 'done' AND sml.date > %(start)s AND sml.date <= %(cutoff)s
                  AND sml.location_id = ANY(%(locs)s) AND NOT (sml.location_dest_id = ANY(%(locs)s))
                  AND sml.product_id = ANY(%(products)s)
                  AND sm.is_inventory IS NOT TRUE
                  AND dest_loc.usage IS DISTINCT FROM 'supplier'
                  AND (
                        sm.scrap_id IS NULL
                        OR EXISTS (
                            SELECT 1 FROM stock_scrap_stock_scrap_reason_tag_rel rel
                            WHERE rel.stock_scrap_id = sm.scrap_id
                              AND rel.stock_scrap_reason_tag_id = ANY(%(reason_tag_ids)s::int[])
                        )
                      )
                GROUP BY sml.product_id
            """, {
                "locs": loc_ids, "cutoff": cutoff, "start": trailing_start,
                "products": list(allowed_product_ids), "reason_tag_ids": reason_tag_ids,
            })
            for product_id, outflow in self.env.cr.fetchall():
                outflow_by_warehouse_product[(warehouse.id, product_id)] = outflow

        # Cost is company-dependent (Harleys has 5 regional companies with genuinely different
        # costs for the same product) - read per warehouse's own company via with_company, one
        # search_read per warehouse rather than a raw SQL read of the underlying jsonb column.
        product_data_by_company = {}
        rows = []
        for location_id, product_id, qty in quant_rows:
            if product_id not in allowed_product_ids:
                continue
            warehouse = location_to_warehouse.get(location_id)
            if not warehouse:
                continue
            company_id = warehouse.company_id.id
            if company_id not in product_data_by_company:
                product_data_by_company[company_id] = {
                    product["id"]: product
                    for product in self.env["product.product"].with_company(company_id).search_read(
                        [("id", "in", list(allowed_product_ids))],
                        ["product_tmpl_id", "categ_id", "uom_id", "default_code", "standard_price"],
                    )
                }
            product = product_data_by_company[company_id].get(product_id)
            if not product:
                continue
            cost = product.get("standard_price") or 0.0
            outflow = outflow_by_warehouse_product.get((warehouse.id, product_id), 0.0)
            avg_daily_usage = outflow / trailing_days
            if adu_visibility == "positive" and avg_daily_usage <= 0:
                continue
            days_of_supply = round(qty / avg_daily_usage, 1) if avg_daily_usage > 0 else None
            rows.append({
                "id": location_id * _WAREHOUSE_ID_MULTIPLIER + product_id,
                "warehouse": warehouse.name,
                "stock_location": location_names.get(location_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._display(product.get("categ_id")).rsplit(" / ", 1)[-1],
                "uom": self._display(product.get("uom_id")),
                "qoh": round(qty, 2),
                "unit_cost": round(cost, 2),
                "total_value": round(qty * cost, 2),
                "avg_daily_usage": avg_daily_usage,
                "days_of_supply": days_of_supply,
            })
        return rows
