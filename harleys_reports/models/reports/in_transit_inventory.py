from odoo.exceptions import ValidationError

from .base import (
    PRODUCT_DISPLAY_FIELDS, PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin,
)
from .registry import register_report

# Row id = location_id * _LOCATION_ID_MULTIPLIER + product_id * _PRODUCT_ID_MULTIPLIER + lot_id.
# Both multipliers comfortably exceed any realistic id range so the components never collide.
_LOCATION_ID_MULTIPLIER = 1_000_000_000_000
_PRODUCT_ID_MULTIPLIER = 1_000_000


@register_report
class InTransitInventoryReport(SqlRowsReportMixin, ReportProvider):
    key = "in_transit_inventory"
    title = "In-Transit Inventory"
    description = "Everything currently sitting in a transit location, by product and lot."
    model_name = "stock.quant"

    filters = (
        PRODUCT_SEARCH_FILTER,
        # Not a warehouse filter - there's no per-warehouse transit location, only a handful of
        # shared hubs.
        {"key": "transit_location_ids", "label": "Transit Locations", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
    )
    columns = (
        {"key": "company", "label": "Company", "type": "text", "sortable": True, "optional": True},
        {"key": "location", "label": "Transit Location", "type": "text", "sortable": True},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True, "optional": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True, "filter_key": "search"},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True, "filter_key": "category_ids"},
        {"key": "lot", "label": "Lot", "type": "text", "sortable": True},
        {"key": "uom", "label": "UOM", "type": "text", "sortable": True},
        {"key": "quantity", "label": "Qty In Transit", "type": "float", "sortable": True, "align": "end"},
        {"key": "reserved_quantity", "label": "Reserved Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "unreserved_quantity", "label": "Unreserved Qty", "type": "float", "sortable": True, "align": "end"},
    )
    relation_filters = {**PRODUCT_RELATION_FILTERS, "transit_location_ids": ("stock.location", [("usage", "=", "transit")])}
    default_sort = {"key": "location", "direction": "asc"}
    sort_fields = {
        "company": "company", "location": "location", "sku": "sku", "product": "product",
        "category": "category", "lot": "lot", "uom": "uom", "quantity": "quantity",
        "reserved_quantity": "reserved_quantity", "unreserved_quantity": "unreserved_quantity",
    }

    def metadata(self):
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": {**self._default_category_filter()},
            "default_sort": self.default_sort,
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
        normalized = {}
        transit_location_ids = values.get("transit_location_ids")
        if transit_location_ids:
            normalized["transit_location_ids"] = self._validate_id_list(transit_location_ids, "transit location")
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
        category_ids = values.get("category_ids")
        search_term = values.get("search")

        # Validated server-side against usage='transit' regardless of what the client sent. No
        # selection at all falls back to every transit location.
        transit_location_ids = values.get("transit_location_ids")
        location_domain = [("usage", "=", "transit")]
        if transit_location_ids:
            location_domain.append(("id", "in", transit_location_ids))
        selected_location_ids = self.env["stock.location"].search(location_domain).ids
        if not selected_location_ids:
            return []

        # No company restriction, deliberately: transit hubs are shared across every company, not
        # owned by one - company_id is NULL on the location and on virtually every quant in it.
        self.env.cr.execute("""
            SELECT
                sq.company_id, sq.location_id, sq.product_id, sq.lot_id,
                SUM(sq.quantity) AS qty, SUM(sq.reserved_quantity) AS reserved_qty
            FROM stock_quant sq
            WHERE sq.location_id = ANY(%(locs)s)
            GROUP BY sq.company_id, sq.location_id, sq.product_id, sq.lot_id
            HAVING SUM(sq.quantity) <> 0
        """, {"locs": selected_location_ids})
        quant_rows = self.env.cr.fetchall()
        if not quant_rows:
            return []

        product_ids = list({product_id for _c, _l, product_id, _lot, _q, _r in quant_rows})
        allowed_product_ids = self._filter_product_ids(product_ids, category_ids, search_term)
        if not allowed_product_ids:
            return []

        # A restricted user can only read res.company records for their own companies - browse
        # only ids known to be readable, anything else falls back to "" rather than raising.
        readable_company_ids = {
            company_id for company_id, _l, _p, _lot, _q, _r in quant_rows if company_id
        } & set(self.env.user.company_ids.ids)
        company_names = {
            company.id: company.name for company in self.env["res.company"].browse(readable_company_ids)
        }
        # sudo() for location/lot names only - every row here is already visible to every user of
        # this report, so a location/lot in another company should still show its name, not raise.
        location_names = {
            location.id: location.complete_name
            for location in self.env["stock.location"].sudo().browse({location_id for _c, location_id, _p, _lot, _q, _r in quant_rows})
        }
        lot_names = {
            lot.id: lot.name
            for lot in self.env["stock.lot"].sudo().browse({lot_id for _c, _l, _p, lot_id, _q, _r in quant_rows if lot_id})
        }
        product_data = {
            product["id"]: product
            for product in self.env["product.product"].search_read(
                [("id", "in", list(allowed_product_ids))], list(PRODUCT_DISPLAY_FIELDS),
            )
        }

        rows = []
        for company_id, location_id, product_id, lot_id, qty, reserved_qty in quant_rows:
            if product_id not in allowed_product_ids:
                continue
            product = product_data.get(product_id)
            if not product:
                continue
            rows.append({
                "id": location_id * _LOCATION_ID_MULTIPLIER + product_id * _PRODUCT_ID_MULTIPLIER + (lot_id or 0),
                "company": company_names.get(company_id, ""),
                "location": location_names.get(location_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._leaf_category(product),
                "lot": lot_names.get(lot_id, ""),
                "uom": self._display(product.get("uom_id")),
                "quantity": round(qty, 2),
                "reserved_quantity": round(reserved_qty, 2),
                "unreserved_quantity": round(qty - reserved_qty, 2),
            })
        return rows
