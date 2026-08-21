from odoo.exceptions import ValidationError

from .base import ReportProvider
from .date_utils import date_boundary

# Curated for the "All Data Models" section of Report Extraction. Every access still goes
# through has_access()/search_read()/fields_get(), so a user only ever sees a model (and its
# fields) they already have normal read access to - this list is a UX curation, not a security
# boundary.
DYNAMIC_MODELS = {
    "sale.order": {"name": "Sales Orders", "description": "Customer orders across all warehouses."},
    "purchase.order": {"name": "Purchase Orders", "description": "Vendor purchase orders across all warehouses."},
    "product.product": {"name": "Products", "description": "Product master with sales price and cost."},
    "stock.move": {"name": "Stock Moves", "description": "Stock movements across locations and warehouses."},
    "account.move": {"name": "Invoices", "description": "Customer invoices and their payment status."},
}

_FIELD_TYPE_MAP = {
    "char": "text", "text": "text", "html": "text",
    "many2one": "many2one",
    "date": "date", "datetime": "datetime",
    "selection": "selection",
    "boolean": "boolean",
    "integer": "numeric", "float": "numeric", "monetary": "numeric",
}
_EXCLUDED_NAMES = {"id", "display_name", "__last_update"}
# Mixin/technical noise (mail.thread, activity, portal, website, sms, rating) - present on most
# business models but never useful in a report; excluded for usability, not security.
_NOISE_NAME_PREFIXES = ("message_", "activity_", "access_", "website_", "portal_", "sms_", "rating_")
# Deprioritized, but not excluded, so the *default* column picks stay meaningful without hiding
# the field entirely from a user who wants it.
_PRIORITY_FIELD_NAMES = (
    "name", "reference", "date_order", "date", "invoice_date", "scheduled_date",
    "partner_id", "state", "payment_state", "amount_total", "amount_untaxed",
    "product_id", "product_qty", "quantity", "user_id", "company_id",
)


def list_dynamic_models(env):
    return [
        {"model": model_name, "name": info["name"]}
        for model_name, info in DYNAMIC_MODELS.items()
        if env[model_name].has_access("read")
    ]


class DynamicModelReport(ReportProvider):
    def __init__(self, env, model_name):
        if model_name not in DYNAMIC_MODELS:
            raise ValidationError("Unknown data model.")
        super().__init__(env)
        self.model_name = model_name
        info = DYNAMIC_MODELS[model_name]
        self.key = f"model:{model_name}"
        self.title = info["name"]
        self.description = info["description"]

    def _field_defs(self):
        fields_data = self.model.fields_get(attributes=["string", "type", "relation", "selection", "store"])
        fields = []
        for name, info in fields_data.items():
            if name in _EXCLUDED_NAMES or name.startswith(_NOISE_NAME_PREFIXES):
                continue
            label = info.get("string") or name
            if "json" in label.lower():
                continue
            mapped = _FIELD_TYPE_MAP.get(info["type"])
            if not mapped:
                continue
            field = {
                "name": name,
                "label": label,
                "type": mapped,
                "store": bool(info.get("store")),
            }
            if info["type"] == "selection":
                field["options"] = [
                    {"value": value, "label": label}
                    for value, label in (info.get("selection") or [])
                    if isinstance(value, str)
                ]
            fields.append(field)
        # Stable sort: known business-relevant fields first (in priority order), everything
        # else keeps fields_get()'s natural order - this is what the frontend uses to pick
        # sensible *default* columns, without hiding any field from the picker.
        fields.sort(key=lambda f: (
            _PRIORITY_FIELD_NAMES.index(f["name"]) if f["name"] in _PRIORITY_FIELD_NAMES else len(_PRIORITY_FIELD_NAMES)
        ))
        return fields

    def metadata(self):
        self.check_source_access()
        return {
            **self.summary(),
            "model": self.model_name,
            "fields": self._field_defs(),
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
        }

    @staticmethod
    def _field_by_name(name, fields_by_name):
        field = fields_by_name.get(name)
        if not field:
            raise ValidationError("Unknown field.")
        return field

    def _validate_columns(self, columns, fields_by_name):
        if not isinstance(columns, list) or not columns:
            raise ValidationError("Select at least one field.")
        for column in columns:
            self._field_by_name(column, fields_by_name)
        return columns

    def _domain(self, columns, filters, fields_by_name):
        if not isinstance(filters, dict):
            raise ValidationError("Invalid filters.")
        domain = []
        for column in columns:
            field = self._field_by_name(column, fields_by_name)
            ftype = field["type"]
            if ftype == "numeric":
                min_value = filters.get(f"{column}__min")
                max_value = filters.get(f"{column}__max")
                if min_value not in (None, ""):
                    domain.append((column, ">=", float(min_value)))
                if max_value not in (None, ""):
                    domain.append((column, "<=", float(max_value)))
                continue
            value = filters.get(column)
            if value in (None, ""):
                continue
            if ftype == "text":
                if not isinstance(value, str) or len(value) > 200:
                    raise ValidationError("Invalid text filter.")
                domain.append((column, "ilike", value))
            elif ftype == "many2one":
                try:
                    m2o_id = int(value)
                except (TypeError, ValueError):
                    raise ValidationError("Invalid filter value.")
                domain.append((column, "=", self._validate_integer(m2o_id, column)))
            elif ftype == "boolean":
                domain.append((column, "=", value in (True, "true", "True")))
            elif ftype == "selection":
                allowed = {opt["value"] for opt in field.get("options", [])}
                if value not in allowed:
                    raise ValidationError("Invalid selection filter.")
                domain.append((column, "=", value))
            elif ftype == "date":
                domain.append((column, "=", value))
            elif ftype == "datetime":
                domain.append((column, ">=", date_boundary(self.env, value)))
                domain.append((column, "<", date_boundary(self.env, value, end=True)))
        return domain

    def _order(self, sort, fields_by_name):
        if not isinstance(sort, dict):
            raise ValidationError("Invalid sort.")
        key = sort.get("key")
        direction = sort.get("direction", "asc")
        field = self._field_by_name(key, fields_by_name)
        if not field["store"] or direction not in ("asc", "desc"):
            raise ValidationError("Unsupported sort.")
        return f"{key} {direction}, id {direction}"

    def _serialize(self, record, columns, fields_by_name):
        row = {"id": record["id"]}
        for column in columns:
            value = record.get(column)
            if fields_by_name[column]["type"] == "many2one" or isinstance(value, (tuple, list)):
                row[column] = self._display(value)
            else:
                row[column] = value if value is not False else ""
        return row

    def get_page(self, columns, filters, offset, limit, sort):
        self.check_source_access()
        offset, limit = self._validate_page(offset, limit)
        fields_by_name = {f["name"]: f for f in self._field_defs()}
        columns = self._validate_columns(columns, fields_by_name)
        domain = self._domain(columns, filters or {}, fields_by_name)
        order = self._order(sort, fields_by_name)
        records = self.model.search_read(domain, columns, offset=offset, limit=limit, order=order)
        total = self.model.search_count(domain)
        return {
            "rows": [self._serialize(record, columns, fields_by_name) for record in records],
            "offset": offset,
            "limit": limit,
            "total": total,
            "has_more": offset + len(records) < total,
        }

    def search_filter_options(self, field_name, term, limit):
        self.check_source_access()
        fields_by_name = {f["name"]: f for f in self._field_defs()}
        field = self._field_by_name(field_name, fields_by_name)
        if field["type"] != "many2one":
            raise ValidationError("Unsupported relational filter.")
        if not isinstance(term, str) or len(term) > 100:
            raise ValidationError("Invalid filter search.")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValidationError("Invalid filter option limit.")
        limit = max(1, min(limit, 40))
        relation = self.model.fields_get([field_name])[field_name]["relation"]
        comodel = self.env[relation]
        if not comodel.has_access("read"):
            return []
        options = comodel.name_search(name=term, operator="ilike", limit=limit)
        return [{"id": record_id, "label": label} for record_id, label in options]

    def columns_meta(self, columns):
        fields_by_name = {f["name"]: f for f in self._field_defs()}
        return [
            {
                "key": column,
                "label": fields_by_name[column]["label"] if column in fields_by_name else column,
                "type": "badge" if fields_by_name.get(column, {}).get("type") == "selection" else "text",
            }
            for column in columns
        ]

    def export_rows(self, columns, filters, sort, row_ids=None):
        self.check_source_access()
        fields_by_name = {f["name"]: f for f in self._field_defs()}
        columns = self._validate_columns(columns, fields_by_name)
        if row_ids:
            rows = []
            batch_size = 1000
            for offset in range(0, len(row_ids), batch_size):
                batch_ids = row_ids[offset:offset + batch_size]
                records = self.model.browse(batch_ids).read(columns)
                rows.extend(self._serialize(record, columns, fields_by_name) for record in records)
            return rows
        domain = self._domain(columns, filters or {}, fields_by_name)
        order = self._order(sort, fields_by_name)
        total = self.model.search_count(domain, limit=self.maximum_export_rows + 1)
        if total > self.maximum_export_rows:
            raise ValidationError(
                f"This export exceeds the {self.maximum_export_rows:,} row limit. Apply more filters and try again."
            )
        rows = []
        batch_size = 1000
        for offset in range(0, total, batch_size):
            records = self.model.search_read(domain, columns, offset=offset, limit=batch_size, order=order)
            rows.extend(self._serialize(record, columns, fields_by_name) for record in records)
        return rows
