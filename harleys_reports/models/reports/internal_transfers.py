from odoo.exceptions import ValidationError

from .base import ReportProvider
from .date_utils import date_boundary
from .registry import register_report


@register_report
class InternalTransfersReport(ReportProvider):
    key = "internal_transfers"
    title = "Internal Transfers"
    description = "Review internal warehouse transfers and stock movement flows."
    model_name = "stock.picking"

    filters = (
        {"key": "date_from", "label": "Date From", "type": "date", "group": "primary"},
        {"key": "date_to", "label": "Date To", "type": "date", "group": "primary"},
        {"key": "reference", "label": "Reference", "type": "text", "group": "primary"},
        {"key": "location_id", "label": "Source Location", "type": "many2one", "group": "primary"},
        {"key": "location_dest_id", "label": "Destination Location", "type": "many2one", "group": "primary"},
        {"key": "company_id", "label": "Company", "type": "many2one", "group": "advanced"},
        {"key": "state", "label": "State", "type": "selection", "group": "advanced", "options": [
            {"value": "", "label": "All states"},
            {"value": "draft", "label": "Draft"},
            {"value": "assigned", "label": "Ready"},
            {"value": "done", "label": "Done"},
            {"value": "cancel", "label": "Cancelled"},
        ]},
    )

    columns = (
        {"key": "date", "label": "Date", "type": "datetime", "sortable": True},
        {"key": "reference", "label": "Reference", "type": "text", "sortable": True},
        {"key": "origin", "label": "Origin", "type": "text", "sortable": True},
        {"key": "source", "label": "Source", "type": "text", "sortable": True},
        {"key": "destination", "label": "Destination", "type": "text", "sortable": True},
        {"key": "company", "label": "Company", "type": "text", "sortable": True},
        {"key": "state", "label": "State", "type": "badge", "sortable": True},
        {"key": "done_by", "label": "Done By", "type": "text", "sortable": True},
        # Hidden by default - available via the Columns picker, same idea as Odoo's own
        # list-view "optional fields" toggle.
        {"key": "contact", "label": "Contact", "type": "text", "sortable": True, "optional": True},
        {"key": "responsible", "label": "Responsible", "type": "text", "sortable": True, "optional": True},
        {"key": "back_order_of", "label": "Back Order Of", "type": "text", "sortable": True, "optional": True,
         "help": "Set when this transfer was split off from an earlier, partially-done one."},
        {"key": "effective_date", "label": "Effective Date", "type": "datetime", "sortable": True, "optional": True,
         "help": "When the transfer was actually completed (vs. Date, which is when it was scheduled)."},
    )

    field_names = (
        "scheduled_date", "name", "origin", "location_id", "location_dest_id",
        "company_id", "state", "date_done", "create_uid",
        "partner_id", "user_id", "backorder_id",
    )

    sort_fields = {
        "date": "scheduled_date",
        "reference": "name",
        "origin": "origin",
        "source": "location_id",
        "destination": "location_dest_id",
        "company": "company_id",
        "state": "state",
        "done_by": "create_uid",
        "contact": "partner_id",
        "responsible": "user_id",
        "back_order_of": "backorder_id",
        "effective_date": "date_done",
    }

    relation_filters = {
        "location_id": ("stock.location", [("usage", "!=", "view")]),
        "location_dest_id": ("stock.location", [("usage", "!=", "view")]),
        "company_id": ("res.company", []),
    }

    allowed_states = {"draft", "assigned", "done", "cancel"}

    def metadata(self):
        company_ids = set(self.env.companies.ids)
        filters = [dict(item) for item in self.filters]
        for item in filters:
            if item["key"] == "company_id":
                item["hidden"] = len(company_ids) <= 1
        return {
            **self.summary(),
            "filters": filters,
            "columns": [dict(column) for column in self.columns],
            "default_filters": {"state": "assigned"},
            "default_sort": {"key": "date", "direction": "desc"},
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
        for key, value in values.items():
            if value in (False, None, ""):
                continue
            if key in self.relation_filters:
                normalized[key] = self._validate_integer(value, key)
            elif key in ("date_from", "date_to"):
                normalized[key] = value
            elif key == "reference":
                if not isinstance(value, str) or len(value) > 200:
                    raise ValidationError("Invalid reference filter.")
                normalized[key] = value.strip()
            elif key == "state":
                if value not in self.allowed_states:
                    raise ValidationError("Invalid state filter.")
                normalized[key] = value
        return normalized

    def _domain(self, values):
        values = self._normalize_filters(values)
        domain = [("picking_type_code", "=", "internal")] + self._location_restriction_domain()
        if values.get("date_from"):
            domain.append(("scheduled_date", ">=", date_boundary(self.env, values["date_from"])))
        if values.get("date_to"):
            domain.append(("scheduled_date", "<", date_boundary(self.env, values["date_to"], end=True)))
        if values.get("reference"):
            domain.append(("name", "ilike", values["reference"]))
        for key in ("location_id", "location_dest_id"):
            if values.get(key):
                domain.append((key, "=", values[key]))
        if values.get("company_id"):
            if values["company_id"] not in self.env.companies.ids:
                raise ValidationError("The selected company is not enabled for this session.")
            domain.append(("company_id", "=", values["company_id"]))
        if values.get("state"):
            domain.append(("state", "=", values["state"]))
        return domain

    def _order(self, sort):
        if not isinstance(sort, dict):
            raise ValidationError("Invalid report sort.")
        key = sort.get("key", "date")
        direction = sort.get("direction", "desc")
        if key not in self.sort_fields or direction not in ("asc", "desc"):
            raise ValidationError("Unsupported report sort.")
        return f"{self.sort_fields[key]} {direction}, id {direction}"

    def _serialize(self, record):
        return {
            "id": record["id"],
            "date": record.get("scheduled_date") or "",
            "reference": record.get("name") or "",
            "origin": record.get("origin") or "",
            "source": self._display(record.get("location_id")),
            "destination": self._display(record.get("location_dest_id")),
            "company": self._display(record.get("company_id")),
            "state": record.get("state") or "",
            "done_by": self._display(record.get("create_uid")),
            "contact": self._display(record.get("partner_id")),
            "responsible": self._display(record.get("user_id")),
            "back_order_of": self._display(record.get("backorder_id")),
            "effective_date": record.get("date_done") or "",
        }

    def get_page(self, filters, offset, limit, sort):
        self.check_source_access()
        offset, limit = self._validate_page(offset, limit)
        domain = self._domain(filters)
        order = self._order(sort)
        records = self.model.search_read(domain, self.field_names, offset=offset, limit=limit, order=order)
        total = self.model.search_count(domain)
        return {
            "rows": [self._serialize(record) for record in records],
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + len(records) < total,
        }

    def search_filter_options(self, filter_key, term, limit):
        self.check_source_access()
        if filter_key not in self.relation_filters:
            raise ValidationError("Unsupported relational filter.")
        if not isinstance(term, str) or len(term) > 100:
            raise ValidationError("Invalid filter search.")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValidationError("Invalid filter option limit.")
        limit = max(1, min(limit, 40))
        model_name, domain = self.relation_filters[filter_key]
        model = self.env[model_name]
        if not model.has_access("read"):
            return []
        if filter_key == "company_id":
            domain = [("id", "in", self.env.companies.ids)]
        elif filter_key in ("location_id", "location_dest_id"):
            allowed_ids = self.env["stock.location"]._get_user_allowed_location_ids().ids
            domain = domain + [("id", "in", allowed_ids)]
        options = model.name_search(name=term, domain=domain, operator="ilike", limit=limit)
        return [{"id": record_id, "label": label} for record_id, label in options]

    def export_rows(self, filters, sort, row_ids=None):
        self.check_source_access()
        if row_ids:
            rows = []
            batch_size = 1000
            restriction = [("picking_type_code", "=", "internal")] + self._location_restriction_domain()
            for offset in range(0, len(row_ids), batch_size):
                batch_ids = row_ids[offset:offset + batch_size]
                records = self.model.search([("id", "in", batch_ids)] + restriction)
                rows.extend(self._serialize(record) for record in records)
            return rows
        domain = self._domain(filters)
        order = self._order(sort)
        total = self.model.search_count(domain, limit=self.maximum_export_rows + 1)
        if total > self.maximum_export_rows:
            raise ValidationError(
                f"This export exceeds the {self.maximum_export_rows:,} row limit. Apply more filters and try again."
            )
        rows = []
        batch_size = 1000
        for offset in range(0, total, batch_size):
            batch = self.model.search_read(domain, self.field_names, offset=offset, limit=batch_size, order=order)
            rows.extend(self._serialize(record) for record in batch)
        return rows
