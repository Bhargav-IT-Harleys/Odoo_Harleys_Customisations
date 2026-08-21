from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError

from .base import ReportProvider
from .date_utils import date_boundary
from .registry import register_report

_TRAILING_DAYS = 30
_WAREHOUSE_ID_MULTIPLIER = 1_000_000


@register_report
class StockReportProvider(ReportProvider):
    key = "stock_report"
    title = "Stock Report"
    description = ""
    model_name = "stock.move.line"

    filters = (
        {"key": "as_of_date", "label": "As Of Date", "type": "date", "group": "primary"},
        {"key": "search", "label": "Search Product / SKU", "type": "text", "group": "primary"},
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary"},
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
    )
    columns = (
        {"key": "date", "label": "Date", "type": "text", "sortable": True,
         "help": "The As Of Date selected for this run - QOH itself is always Odoo's current live balance; this date only sets the trailing window used for ADU/DOS."},
        {"key": "warehouse", "label": "Location", "type": "text", "sortable": True,
         "help": "The outlet/warehouse this stock belongs to."},
        {"key": "product", "label": "Product", "type": "text", "sortable": True,
         "help": "Product name."},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True,
         "help": "The product's category (leaf level)."},
        {"key": "qoh", "label": "QOH", "type": "float", "sortable": True, "align": "end",
         "help": "Current Quantity On Hand as maintained by Odoo (stock.quant) - the same figure shown in Inventory > Reporting > Stock, summed across lots/packages."},
        {"key": "unit_cost", "label": "Unit Cost", "type": "float", "sortable": True, "align": "end",
         "help": "The product's current standard cost in this outlet's company."},
        {"key": "total_value", "label": "Total Value", "type": "float", "sortable": True, "align": "end",
         "help": "QOH x Unit Cost."},
        {"key": "avg_daily_usage", "label": "ADU (draft)", "type": "float", "sortable": True, "align": "end",
         "help": "Draft: average daily usage, trailing 30 days, excluding inventory adjustments and vendor returns."},
        {"key": "days_of_supply", "label": "DOS (draft)", "type": "float", "sortable": True, "align": "end",
         "help": "Draft: Days of Supply = QOH / Average Daily Usage. Blank when there is no recent usage to project from."},
        # Hidden by default - the underlying product/move models carry many more fields than
        # fit a default view. Exposed as optional columns, toggled from the Columns picker,
        # same idea as Odoo's own list-view "optional fields" toggle.
        {"key": "sku", "label": "SKU", "type": "text", "sortable": True, "optional": True,
         "help": "Product internal reference."},
        {"key": "barcode", "label": "Barcode", "type": "text", "sortable": True, "optional": True,
         "help": "Product barcode."},
        {"key": "uom", "label": "UoM", "type": "text", "sortable": True, "optional": True,
         "help": "Unit of measure."},
        {"key": "product_type", "label": "Product Type", "type": "badge", "sortable": True, "optional": True,
         "help": "Goods, Service, or Combo.",
         "options": [
             {"value": "consu", "label": "Goods"},
             {"value": "service", "label": "Service"},
             {"value": "combo", "label": "Combo"},
         ]},
        {"key": "sales_price", "label": "Sales Price", "type": "float", "sortable": True, "align": "end", "optional": True,
         "help": "Current sales price in this outlet's company."},
        {"key": "weight", "label": "Weight (kg)", "type": "float", "sortable": True, "align": "end", "optional": True,
         "help": "Product weight."},
    )
    relation_filters = {
        "category_ids": ("product.category", []),
        "warehouse_ids": ("stock.warehouse", []),
    }
    sort_fields = {
        "date": "date", "warehouse": "warehouse", "product": "product", "category": "category",
        "qoh": "qoh", "unit_cost": "unit_cost", "total_value": "total_value",
        "avg_daily_usage": "avg_daily_usage", "days_of_supply": "days_of_supply",
        "sku": "sku", "barcode": "barcode", "uom": "uom", "product_type": "product_type",
        "sales_price": "sales_price", "weight": "weight",
    }

    def metadata(self):
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": {"as_of_date": fields.Date.to_string(fields.Date.context_today(self.model))},
            "default_sort": {"key": "warehouse", "direction": "asc"},
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
            "export_formats": ["csv", "xlsx"],
        }

    def _normalize_filters(self, values):
        if not isinstance(values, dict):
            raise ValidationError("Invalid report filters.")
        allowed = {item["key"] for item in self.filters}
        if set(values) - allowed:
            raise ValidationError("Unsupported report filter.")
        if not values.get("as_of_date"):
            raise ValidationError("Select a date.")
        normalized = {"as_of_date": values["as_of_date"]}
        for key, label in (("warehouse_ids", "warehouse"), ("category_ids", "category")):
            value = values.get(key)
            if value:
                normalized[key] = self._validate_id_list(value, label)
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        return normalized

    @staticmethod
    def _validate_id_list(value, label):
        if not isinstance(value, list):
            raise ValidationError(f"Invalid {label} selection.")
        ids = []
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
                raise ValidationError(f"Invalid {label} id.")
            ids.append(item)
        return ids

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        warehouses = self._resolve_warehouses(values.get("warehouse_ids"))
        if not warehouses:
            return []
        cutoff = date_boundary(self.env, values["as_of_date"], end=True)
        trailing_start = cutoff - timedelta(days=_TRAILING_DAYS)
        category_ids = values.get("category_ids")
        search_term = values.get("search")

        rows = []
        for warehouse in warehouses:
            loc_ids = self._warehouse_location_ids(warehouse)
            if not loc_ids:
                continue

            # QOH is Odoo's own maintained on-hand balance (stock.quant), not an independent
            # reconstruction from move history - same figure as Inventory > Reporting > Stock.
            # Summed across lots/packages/owners so a lot-tracked product still yields one row
            # per product, matching that standard report.
            self.env.cr.execute("""
                SELECT product_id, COALESCE(SUM(quantity), 0) AS qty
                FROM stock_quant
                WHERE location_id = ANY(%(locs)s)
                GROUP BY product_id
            """, {"locs": loc_ids})
            qty_by_product = dict(self.env.cr.fetchall())
            if not qty_by_product:
                continue
            product_ids = list(qty_by_product.keys())

            if category_ids:
                product_ids = self.env["product.product"].search([
                    ("id", "in", product_ids), ("categ_id", "child_of", category_ids),
                ]).ids
                if not product_ids:
                    continue

            if search_term:
                product_ids = self.env["product.product"].search([
                    ("id", "in", product_ids),
                    "|", ("display_name", "ilike", search_term), ("default_code", "ilike", search_term),
                ]).ids
                if not product_ids:
                    continue

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
                GROUP BY sml.product_id
            """, {"locs": loc_ids, "cutoff": cutoff, "start": trailing_start, "products": product_ids})
            outflow_by_product = dict(self.env.cr.fetchall())

            product_data = self.env["product.product"].with_company(warehouse.company_id.id).search_read(
                [("id", "in", product_ids)],
                ["display_name", "categ_id", "standard_price", "default_code", "barcode",
                 "uom_id", "type", "list_price", "weight"],
            )
            for product in product_data:
                product_id = product["id"]
                qty = qty_by_product[product_id]
                cost = product["standard_price"] or 0.0
                outflow = outflow_by_product.get(product_id, 0.0)
                avg_daily_usage = outflow / _TRAILING_DAYS
                days_of_supply = round(qty / avg_daily_usage, 1) if avg_daily_usage > 0 else None
                rows.append({
                    "id": warehouse.id * _WAREHOUSE_ID_MULTIPLIER + product_id,
                    "date": values["as_of_date"],
                    "warehouse": warehouse.name,
                    "product": product["display_name"],
                    "category": self._display(product.get("categ_id")).rsplit(" / ", 1)[-1],
                    "qoh": round(qty, 2),
                    "unit_cost": round(cost, 2),
                    "total_value": round(qty * cost, 2),
                    "avg_daily_usage": round(avg_daily_usage, 2),
                    "days_of_supply": days_of_supply,
                    "sku": product.get("default_code") or "",
                    "barcode": product.get("barcode") or "",
                    "uom": self._display(product.get("uom_id")),
                    "product_type": product.get("type"),
                    "sales_price": round(product.get("list_price") or 0.0, 2),
                    "weight": product.get("weight") or 0.0,
                })
        return rows

    def _sort_rows(self, rows, sort):
        if not isinstance(sort, dict):
            raise ValidationError("Invalid report sort.")
        key = sort.get("key", "warehouse")
        direction = sort.get("direction", "asc")
        if key not in self.sort_fields or direction not in ("asc", "desc"):
            raise ValidationError("Unsupported report sort.")
        field = self.sort_fields[key]
        return sorted(rows, key=lambda row: (row[field] is None, row[field]), reverse=direction == "desc")

    def get_page(self, filters, offset, limit, sort):
        self.check_source_access()
        offset, limit = self._validate_page(offset, limit)
        rows = self._sort_rows(self._build_rows(filters), sort)
        total = len(rows)
        page = rows[offset:offset + limit]
        return {
            "rows": page,
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + len(page) < total,
        }

    def search_filter_options(self, filter_key, term, limit):
        self.check_source_access()
        if filter_key not in self.relation_filters:
            raise ValidationError("Unsupported relational filter.")
        if not isinstance(term, str) or len(term) > 100:
            raise ValidationError("Invalid filter search.")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValidationError("Invalid filter option limit.")
        limit = max(1, min(limit, 200))
        if filter_key == "warehouse_ids":
            warehouses = self._allowed_warehouses()
            if term:
                term_lower = term.lower()
                warehouses = warehouses.filtered(lambda warehouse: term_lower in warehouse.name.lower())
            warehouses = warehouses.sorted("name")[:limit]
            return [{"id": warehouse.id, "label": warehouse.name} for warehouse in warehouses]
        model_name, domain = self.relation_filters[filter_key]
        model = self.env[model_name]
        if not model.has_access("read"):
            return []
        options = model.name_search(name=term, domain=domain, operator="ilike", limit=limit)
        return [{"id": record_id, "label": label} for record_id, label in options]

    def export_rows(self, filters, sort, row_ids=None):
        self.check_source_access()
        rows = self._build_rows(filters)
        if row_ids:
            row_id_set = set(row_ids)
            rows = [row for row in rows if row["id"] in row_id_set]
        else:
            rows = self._sort_rows(rows, sort)
        if len(rows) > self.maximum_export_rows:
            raise ValidationError(
                f"This export exceeds the {self.maximum_export_rows:,} row limit. "
                "Narrow the warehouse selection or date and try again."
            )
        return rows
