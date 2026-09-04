import math
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
_DEFAULT_REQ_QTY_POLICY_DAYS = 15
_ALLOWED_REQ_QTY_POLICY_DAYS = ("15", "30")
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
        # An empty selection here is meaningful: exclude every scrap/Inv Adjustment move from ADU
        # (see _default_reason_tag_filter), not "show all".
        {"key": "reason_tag_ids", "label": "Inv Adj Reason", "type": "multi_relation", "group": "advanced"},
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
        {"key": "req_qty_policy", "label": "Inv Stock Policy", "type": "selection", "group": "advanced",
         "required": True,
         "options": [
             {"value": "15", "label": "15 Days"},
             {"value": "30", "label": "30 Days"},
         ]},
    )
    columns = (
        {"key": "warehouse", "label": "Warehouse", "type": "text", "sortable": True, "filter_key": "warehouse_ids"},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True, "optional": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True, "filter_key": "search"},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True, "filter_key": "category_ids"},
        {"key": "uom", "label": "UoM", "type": "text", "sortable": True},
        {"key": "qoh", "label": "Quantity", "type": "float", "sortable": True, "align": "end"},
        {"key": "unit_cost", "label": "Unit Cost", "type": "float", "sortable": True, "align": "end"},
        {"key": "total_value", "label": "Stock Value", "type": "float", "sortable": True, "align": "end"},
        {"key": "avg_daily_usage", "label": "ADU", "type": "float", "sortable": True, "align": "end"},
        {"key": "days_of_supply", "label": "DOS", "type": "float", "sortable": True, "align": "end"},
        {"key": "req_qty", "label": "Req Qty", "type": "float", "sortable": True, "align": "end", "decimals": 4},
        # Hidden by default - available via the Columns picker, same idea as Odoo's own
        # list-view "optional fields" toggle.
        {"key": "stock_location", "label": "Stock Location", "type": "text", "sortable": True, "optional": True},
    )
    relation_filters = {**PRODUCT_RELATION_FILTERS, "reason_tag_ids": ("stock.scrap.reason.tag", [])}
    # Scrap ("Inv Adjustments") moves only count toward ADU when tagged with one of these reasons -
    # Consumed/R&D are genuine usage, everything else (Damaged, Expired, wastage...) defaults out.
    default_reason_tag_names = ("Consumed", "R&D")
    default_sort = {"key": "days_of_supply", "direction": "asc"}
    sort_fields = {
        "warehouse": "warehouse", "stock_location": "stock_location", "sku": "sku",
        "product": "product", "category": "category", "uom": "uom",
        "qoh": "qoh", "unit_cost": "unit_cost", "total_value": "total_value",
        "avg_daily_usage": "avg_daily_usage", "days_of_supply": "days_of_supply", "req_qty": "req_qty",
    }

    def _default_reason_tag_filter(self):
        # Always emit the key, even as [] - an omitted key means "select every option" on the
        # frontend, which here means counting every scrap reason as ADU consumption again.
        ids = self._default_ids_for_names("stock.scrap.reason.tag", self.default_reason_tag_names)
        return {"reason_tag_ids": ids}

    def metadata(self):
        default_filters = {
            "adu_window": str(_DEFAULT_TRAILING_DAYS),
            "adu_visibility": _DEFAULT_ADU_VISIBILITY,
            "req_qty_policy": str(_DEFAULT_REQ_QTY_POLICY_DAYS),
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
                "entirely, or add reasons like Damaged/Expired/wastage to count those too. "
                "Req Qty is how much to order to cover Inv Stock Policy's window at the current "
                "ADU, minus what's already on hand - rounded up, never negative."
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
        # An explicit [] is meaningful here and must be told apart from "key not sent at all",
        # which falls back to the Consumed/R&D default instead of excluding everything.
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
        req_qty_policy = values.get("req_qty_policy")
        normalized["req_qty_policy"] = (
            req_qty_policy if req_qty_policy in _ALLOWED_REQ_QTY_POLICY_DAYS else str(_DEFAULT_REQ_QTY_POLICY_DAYS)
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
        policy_days = int(values["req_qty_policy"])
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

        # Presence-first: only locations that actually hold stock right now, not the full product
        # catalog padded with zeros. One flat query across every selected warehouse's locations.
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
        allowed_product_ids = self._filter_product_ids(product_ids, category_ids, search_term)
        if not allowed_product_ids:
            return []

        location_names = {
            location.id: location.complete_name
            for location in self.env["stock.location"].browse({location_id for location_id, _p, _q in quant_rows})
        }

        # Stays scoped to each warehouse's OWN locations, not the combined set above - a transfer
        # from warehouse A to warehouse B must still count as outflow for A when both are selected.
        outflow_by_warehouse_product = {}
        for warehouse in warehouses:
            loc_ids = self._warehouse_location_ids(warehouse)
            if not loc_ids:
                continue
            # A plain move (scrap_id IS NULL) counts as before; a scrap-linked move only counts if
            # tagged with a selected reason, so an empty reason_tag_ids excludes every scrap move.
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

        # Cost is company-dependent (5 regional companies price the same product differently), so
        # read per warehouse's own company via with_company rather than a single flat search.
        product_data_by_company = {}
        rows = []
        for location_id, product_id, qty in quant_rows:
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
            outflow = outflow_by_warehouse_product.get((warehouse.id, product_id), 0.0)
            avg_daily_usage = outflow / trailing_days
            if adu_visibility == "positive" and avg_daily_usage <= 0:
                continue
            days_of_supply = round(qty / avg_daily_usage, 1) if avg_daily_usage > 0 else None
            req_qty = max(0, math.ceil(policy_days * avg_daily_usage - qty))
            rows.append({
                "id": location_id * _WAREHOUSE_ID_MULTIPLIER + product_id,
                "warehouse": warehouse.name,
                "stock_location": location_names.get(location_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._leaf_category(product),
                "uom": self._display(product.get("uom_id")),
                "qoh": round(qty, 2),
                "unit_cost": round(cost, 2),
                "total_value": round(qty * cost, 2),
                "avg_daily_usage": avg_daily_usage,
                "days_of_supply": days_of_supply,
                "req_qty": req_qty,
            })
        return rows
