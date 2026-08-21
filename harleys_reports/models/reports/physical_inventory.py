from odoo import fields
from odoo.exceptions import ValidationError

from .base import ReportProvider
from .date_utils import date_boundary
from .registry import register_report


@register_report
class PhysicalInventoryReport(ReportProvider):
    key = "physical_inventory"
    title = "Physical Inventory"
    description = "Which outlets performed a physical stock count on a given date, who did it, and when."
    model_name = "stock.move.line"

    filters = (
        {"key": "date", "label": "Date", "type": "date", "group": "primary"},
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary"},
    )
    columns = (
        {"key": "warehouse", "label": "Outlet", "type": "text", "sortable": True},
        {"key": "status", "label": "Status", "type": "badge", "sortable": True, "options": [
            {"value": "done", "label": "Done"},
            {"value": "pending", "label": "Pending"},
        ]},
        {"key": "done_by", "label": "Done By", "type": "text", "sortable": True},
        {"key": "timestamp", "label": "Timestamp", "type": "datetime", "sortable": True},
        # Hidden by default - available via the Columns picker, same idea as Odoo's own
        # list-view "optional fields" toggle.
        {"key": "lines_counted", "label": "Lines Counted", "type": "float", "sortable": True, "align": "end",
         "optional": True, "help": "Number of inventory-adjustment move lines recorded for this outlet that day."},
        {"key": "net_adjustment", "label": "Net Qty Adjusted", "type": "float", "sortable": True, "align": "end",
         "optional": True, "help": "Net quantity change from the count: positive if more stock was found than expected, negative if less."},
        {"key": "last_updated", "label": "Last Updated", "type": "datetime", "sortable": True, "optional": True,
         "help": "The most recent count entry that day (Timestamp shows the first)."},
    )
    relation_filters = {
        "warehouse_ids": ("stock.warehouse", []),
    }
    sort_fields = {
        "warehouse": "warehouse", "status": "status", "done_by": "done_by", "timestamp": "timestamp",
        "lines_counted": "lines_counted", "net_adjustment": "net_adjustment", "last_updated": "last_updated",
    }

    def metadata(self):
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": {"date": fields.Date.to_string(fields.Date.context_today(self.model))},
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
        if not values.get("date"):
            raise ValidationError("Select a date.")
        normalized = {"date": values["date"]}
        warehouse_ids = values.get("warehouse_ids")
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                raise ValidationError("Invalid warehouse selection.")
            ids = []
            for value in warehouse_ids:
                if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                    raise ValidationError("Invalid warehouse id.")
                ids.append(value)
            normalized["warehouse_ids"] = ids
        return normalized

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        warehouses = self._resolve_warehouses(values.get("warehouse_ids"))
        if not warehouses:
            return []
        start = date_boundary(self.env, values["date"])
        end = date_boundary(self.env, values["date"], end=True)

        location_to_warehouse = {}
        all_location_ids = []
        for warehouse in warehouses:
            for location_id in self._warehouse_location_ids(warehouse):
                location_to_warehouse[location_id] = warehouse
                all_location_ids.append(location_id)
        if not all_location_ids:
            return []

        self.env.cr.execute("""
            SELECT sml.location_id, sml.location_dest_id, sml.create_uid, sml.date, sml.quantity
            FROM stock_move_line sml
            JOIN stock_move sm ON sm.id = sml.move_id
            WHERE sm.is_inventory = true AND sml.state = 'done'
              AND sml.date >= %(start)s AND sml.date < %(end)s
              AND (sml.location_id = ANY(%(locs)s) OR sml.location_dest_id = ANY(%(locs)s))
        """, {"locs": all_location_ids, "start": start, "end": end})

        info_by_warehouse = {}
        for location_id, location_dest_id, user_id, moved_at, quantity in self.env.cr.fetchall():
            warehouse = location_to_warehouse.get(location_id) or location_to_warehouse.get(location_dest_id)
            if not warehouse:
                continue
            entry = info_by_warehouse.setdefault(warehouse.id, {
                "user_ids": set(), "first": moved_at, "last": moved_at, "lines": 0, "net": 0.0,
            })
            entry["user_ids"].add(user_id)
            entry["first"] = min(entry["first"], moved_at)
            entry["last"] = max(entry["last"], moved_at)
            entry["lines"] += 1
            # Same netting convention as the Stock Report QOH calc: only the end that's inside
            # this warehouse's own locations counts, so it's "how much the count changed
            # on-hand stock by", not raw move volume.
            if location_dest_id in location_to_warehouse:
                entry["net"] += quantity
            if location_id in location_to_warehouse:
                entry["net"] -= quantity

        all_user_ids = {uid for entry in info_by_warehouse.values() for uid in entry["user_ids"]}
        user_names = {user.id: user.name for user in self.env["res.users"].browse(all_user_ids)}

        rows = []
        for warehouse in warehouses:
            entry = info_by_warehouse.get(warehouse.id)
            if entry:
                done_by = ", ".join(sorted(user_names.get(uid, "") for uid in entry["user_ids"]))
                rows.append({
                    "id": warehouse.id,
                    "warehouse": warehouse.name,
                    "status": "done",
                    "done_by": done_by,
                    "timestamp": fields.Datetime.to_string(entry["first"]),
                    "lines_counted": entry["lines"],
                    "net_adjustment": round(entry["net"], 2),
                    "last_updated": fields.Datetime.to_string(entry["last"]),
                })
            else:
                rows.append({
                    "id": warehouse.id,
                    "warehouse": warehouse.name,
                    "status": "pending",
                    "done_by": "",
                    "timestamp": "",
                    "lines_counted": 0,
                    "net_adjustment": 0.0,
                    "last_updated": "",
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
        warehouses = self._allowed_warehouses()
        if term:
            term_lower = term.lower()
            warehouses = warehouses.filtered(lambda warehouse: term_lower in warehouse.name.lower())
        warehouses = warehouses.sorted("name")[:limit]
        return [{"id": warehouse.id, "label": warehouse.name} for warehouse in warehouses]

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
                "Narrow the warehouse selection and try again."
            )
        return rows
