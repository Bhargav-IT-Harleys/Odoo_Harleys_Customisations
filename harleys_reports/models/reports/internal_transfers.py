from odoo.exceptions import ValidationError

from .base import OrmSearchReportMixin, ReportProvider
from .date_utils import date_boundary, to_local_string
from .registry import register_report


@register_report
class InternalTransfersReport(OrmSearchReportMixin, ReportProvider):
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
        {"key": "contact", "label": "Contact", "type": "text", "sortable": True, "optional": True},
        {"key": "responsible", "label": "Responsible", "type": "text", "sortable": True, "optional": True},
        {"key": "back_order_of", "label": "Back Order Of", "type": "text", "sortable": True, "optional": True},
        {"key": "effective_date", "label": "Effective Date", "type": "datetime", "sortable": True, "optional": True},
    )

    field_names = (
        "scheduled_date", "name", "origin", "location_id", "location_dest_id",
        "company_id", "state", "date_done",
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
    default_sort = {"key": "date", "direction": "desc"}

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
            "default_filters": {},
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

    def _serialize(self, record):
        return {
            "id": record["id"],
            "date": to_local_string(self.env, record.get("scheduled_date")),
            "reference": record.get("name") or "",
            "origin": record.get("origin") or "",
            "source": self._display(record.get("location_id")),
            "destination": self._display(record.get("location_dest_id")),
            "company": self._display(record.get("company_id")),
            "state": record.get("state") or "",
            "contact": self._display(record.get("partner_id")),
            "responsible": self._display(record.get("user_id")),
            "back_order_of": self._display(record.get("backorder_id")),
            "effective_date": to_local_string(self.env, record.get("date_done")),
        }

    # A picking id in row_ids could belong to any transfer type - the base location gate alone
    # isn't enough, since this report's own domain is also scoped to picking_type_code=internal.
    def _export_restriction_domain(self):
        return [("picking_type_code", "=", "internal")] + self._location_restriction_domain()
