from odoo.exceptions import ValidationError

from .base import PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin
from .registry import register_report

_LOCATION_ID_MULTIPLIER = 1_000_000
_STATUS_OPTIONS = (
    {"value": "expired", "label": "Expired"},
    {"value": "expires_today", "label": "Expires Today"},
    {"value": "days_1_7", "label": "1-7 Days"},
    {"value": "days_8_15", "label": "8-15 Days"},
    {"value": "days_16_30", "label": "16-30 Days"},
    {"value": "days_31_45", "label": "31-45 Days"},
)


@register_report
class ExpiryReport(SqlRowsReportMixin, ReportProvider):
    key = "expiry_report"
    title = "Expiry Report"
    description = "Lots expiring within 45 days or already expired, with quantity on hand and location."
    model_name = "stock.lot"

    filters = (
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        PRODUCT_SEARCH_FILTER,
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
        {"key": "status", "label": "Status", "type": "selection", "group": "primary",
         "options": [{"value": "", "label": "All"}, *_STATUS_OPTIONS]},
    )
    columns = (
        {"key": "warehouse", "label": "Warehouse", "type": "text", "sortable": True, "optional": True},
        {"key": "location", "label": "Location", "type": "text", "sortable": True},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True, "optional": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True},
        {"key": "lot", "label": "Lot", "type": "text", "sortable": True},
        {"key": "uom", "label": "UOM", "type": "text", "sortable": True},
        {"key": "quantity", "label": "Quantity", "type": "float", "sortable": True, "align": "end"},
        {"key": "expiration_date", "label": "Expiration Date", "type": "text", "sortable": True},
        {"key": "days_to_expiry", "label": "Days to Exp", "type": "float", "sortable": True, "align": "end",
         "help": "Negative means already expired."},
        {"key": "status", "label": "Status", "type": "badge", "sortable": True, "options": list(_STATUS_OPTIONS)},
    )
    relation_filters = PRODUCT_RELATION_FILTERS
    default_sort = {"key": "expiration_date", "direction": "asc"}
    sort_fields = {
        "warehouse": "warehouse", "location": "location", "sku": "sku", "product": "product",
        "category": "category", "lot": "lot", "uom": "uom", "quantity": "quantity",
        "expiration_date": "expiration_date", "days_to_expiry": "days_to_expiry", "status": "status",
    }
    allowed_statuses = {option["value"] for option in _STATUS_OPTIONS}

    def metadata(self):
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": {},
            "default_sort": self.default_sort,
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
            "export_formats": ["csv", "xlsx"],
            "sidebar_note": "Lots with zero or negative quantity on hand are ignored and not included.",
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
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        status = values.get("status")
        if status:
            if status not in self.allowed_statuses:
                raise ValidationError("Invalid status filter.")
            normalized["status"] = status
        return normalized

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        warehouses = self._resolve_warehouses(values.get("warehouse_ids"))
        if not warehouses:
            return []
        category_ids = values.get("category_ids")
        search_term = values.get("search")
        status_filter = values.get("status")

        location_to_warehouse = {}
        all_location_ids = []
        for warehouse in warehouses:
            for location_id in self._warehouse_location_ids(warehouse):
                location_to_warehouse[location_id] = warehouse
                all_location_ids.append(location_id)
        if not all_location_ids:
            return []

        # expiration_date is stored as a UTC datetime - converting through IST before truncating
        # to a date avoids an off-by-one-day error for Indian users, per Raj's own spec. The
        # 45-day cutoff and day-bucket boundaries also match his spec exactly.
        self.env.cr.execute("""
            WITH expiry_stock AS (
                SELECT sq.location_id, sq.product_id, sq.lot_id, SUM(sq.quantity) AS qty,
                       (lot.expiration_date AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Kolkata')::date AS expiration_date
                FROM stock_quant sq
                JOIN stock_lot lot ON lot.id = sq.lot_id
                WHERE sq.location_id = ANY(%(locs)s) AND lot.expiration_date IS NOT NULL
                GROUP BY sq.location_id, sq.product_id, sq.lot_id, lot.expiration_date
                HAVING SUM(sq.quantity) > 0
            )
            SELECT location_id, product_id, lot_id, qty, expiration_date,
                   expiration_date - CURRENT_DATE AS days_to_expiry,
                   CASE
                       WHEN expiration_date < CURRENT_DATE THEN 'expired'
                       WHEN expiration_date = CURRENT_DATE THEN 'expires_today'
                       WHEN expiration_date <= CURRENT_DATE + 7 THEN 'days_1_7'
                       WHEN expiration_date <= CURRENT_DATE + 15 THEN 'days_8_15'
                       WHEN expiration_date <= CURRENT_DATE + 30 THEN 'days_16_30'
                       WHEN expiration_date <= CURRENT_DATE + 45 THEN 'days_31_45'
                   END AS status
            FROM expiry_stock
            WHERE expiration_date <= CURRENT_DATE + 45
        """, {"locs": all_location_ids})
        lot_rows = self.env.cr.fetchall()
        if not lot_rows:
            return []

        product_ids = list({row[1] for row in lot_rows})
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
            for location in self.env["stock.location"].browse({row[0] for row in lot_rows})
        }
        lot_names = {
            lot.id: lot.name
            for lot in self.env["stock.lot"].browse({row[2] for row in lot_rows})
        }

        # Category/UoM aren't company-dependent, but batching per warehouse's own company keeps
        # this consistent with how every other report in this module resolves product data.
        product_data_by_company = {}
        rows = []
        for location_id, product_id, lot_id, qty, expiration_date, days_to_expiry, status in lot_rows:
            if product_id not in allowed_product_ids:
                continue
            if status_filter and status != status_filter:
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
                        ["product_tmpl_id", "categ_id", "uom_id", "default_code"],
                    )
                }
            product = product_data_by_company[company_id].get(product_id)
            if not product:
                continue
            rows.append({
                "id": location_id * _LOCATION_ID_MULTIPLIER + lot_id,
                "warehouse": warehouse.name,
                "location": location_names.get(location_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._display(product.get("categ_id")).rsplit(" / ", 1)[-1],
                "lot": lot_names.get(lot_id, ""),
                "uom": self._display(product.get("uom_id")),
                "quantity": round(qty, 2),
                "expiration_date": expiration_date.isoformat(),
                "days_to_expiry": days_to_expiry,
                "status": status,
            })
        return rows
