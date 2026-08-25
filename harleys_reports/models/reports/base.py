from odoo.exceptions import AccessError, ValidationError

# Shared by every SQL-built report (Stock Report, Physical Inventory, Expiry Report): Warehouses
# (unfiltered) and top-level Product Categories only - the full category tree is too granular to
# pick from directly, and child_of in each report's _build_rows still matches every descendant
# once a parent is selected.
PRODUCT_RELATION_FILTERS = {
    "warehouse_ids": ("stock.warehouse", []),
    "category_ids": ("product.category", [("parent_id", "=", False)]),
}

# Also shared by every SQL-built report: a free-text product/SKU search. "lookup" tells the
# frontend to show it as a type-ahead (applies once a suggestion is picked, not on every
# keystroke); "quick_search_only" keeps it out of the sidebar's own filter list since it's
# reachable through the unified Quick Search bar instead.
PRODUCT_SEARCH_FILTER = {
    "key": "search", "label": "Search Product / SKU", "type": "text", "group": "primary",
    "lookup": True, "quick_search_only": True,
}


class ReportProvider:
    key = None
    title = None
    description = None
    model_name = None
    default_page_size = 80
    page_sizes = (40, 80, 200)
    # Odoo's own list views don't hard-cap the pager either (you can type "1-17060" and it will
    # load exactly that) - this is a sanity backstop against a pathological request, not an
    # artificial "you can't have more than a couple hundred rows" limit. Matches the same ceiling
    # already used for exports.
    maximum_export_rows = 50000
    maximum_page_size = maximum_export_rows
    # {"key": ..., "direction": ...} - the sort every report falls back to when none is given,
    # and what metadata() advertises to the frontend as the initial sort. Set per-report.
    default_sort = {"key": "id", "direction": "asc"}
    # Root category names whose ids should be pre-selected in the Product Categories filter by
    # default (see _default_category_filter) - empty means no default selection.
    default_category_names = ()

    def __init__(self, env):
        self.env = env

    def _default_category_filter(self):
        if not self.default_category_names:
            return {}
        ids = self.env["product.category"].search([
            ("parent_id", "=", False), ("name", "in", list(self.default_category_names)),
        ]).ids
        return {"category_ids": ids} if ids else {}

    @property
    def model(self):
        return self.env[self.model_name]

    def check_source_access(self):
        if not self.model.has_access("read"):
            raise AccessError(f"You do not have read access to {self.title} data.")

    def summary(self):
        return {"key": self.key, "title": self.title, "description": self.description}

    def _validate_page(self, offset, limit):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValidationError("Invalid report offset.")
        # page_sizes are just the quick-pick presets shown in the UI, like Odoo's own list-view
        # pager - any positive size up to maximum_page_size is valid, not only the presets.
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValidationError("Invalid report page size.")
        return offset, min(limit, self.maximum_page_size)

    @staticmethod
    def _validate_integer(value, label):
        if value in (False, None, ""):
            return False
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValidationError(f"Invalid {label} value.")
        return value

    @staticmethod
    def _display(value):
        return value[1] if isinstance(value, (tuple, list)) and len(value) > 1 else ""

    def _location_restriction_domain(self):
        # Mirrors harleys_customization's location gate for standard stock screens - restricted
        # users only see records touching a location they're allowed into. OR'd across both
        # source and destination, since a record can be relevant via either end (e.g. an
        # incoming receipt's source is always a vendor/transit location, never one of the
        # user's own internal locations).
        allowed_ids = self.env["stock.location"]._get_user_allowed_location_ids().ids
        return ["|", ("location_id", "in", allowed_ids), ("location_dest_id", "in", allowed_ids)]

    def _allowed_warehouses(self):
        # Same gate, at warehouse granularity - a restricted user's allowed_warehouse_ids field
        # (from user_warehouse_restriction) already *is* their allowed warehouse set directly,
        # no need to reverse-map from locations. Unrestricted users fall back to every warehouse
        # with a code in a company they currently have enabled.
        user = self.env.user
        allowed = getattr(user, "allowed_warehouse_ids", self.env["stock.warehouse"])
        if allowed:
            return allowed
        return self.env["stock.warehouse"].search([
            ("code", "!=", False),
            ("company_id", "in", self.env.companies.ids),
        ])

    def _resolve_warehouses(self, requested_ids=None):
        # Never trust client-supplied warehouse ids blindly - intersect with what this user is
        # actually allowed to see. An empty/missing selection means "all allowed", not "none".
        allowed = self._allowed_warehouses()
        if requested_ids:
            requested_set = set(requested_ids)
            return allowed.filtered(lambda warehouse: warehouse.id in requested_set)
        return allowed

    def _warehouse_location_ids(self, warehouse):
        return self.env["stock.location"].search([
            ("id", "child_of", warehouse.view_location_id.id),
            ("usage", "=", "internal"),
        ]).ids


class SqlRowsReportMixin:
    """Shared get_page/export_rows/search_filter_options for reports that build their whole
    matching row set from raw SQL in _build_rows(filters) and sort/paginate it in Python -
    Stock Report, Physical Inventory, Expiry Report. Each subclass only needs to implement
    _build_rows and _normalize_filters, and define sort_fields/relation_filters/default_sort.
    """

    # Plugged into the "row limit exceeded" message on export - override for a report whose
    # filters aren't just a warehouse selection (e.g. Physical Inventory also has a date range).
    export_row_limit_hint = "warehouse selection"

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

    def _sort_rows(self, rows, sort):
        if not isinstance(sort, dict):
            raise ValidationError("Invalid report sort.")
        key = sort.get("key", self.default_sort["key"])
        direction = sort.get("direction", self.default_sort["direction"])
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
                f"Narrow the {self.export_row_limit_hint} and try again."
            )
        return rows

    def search_filter_options(self, filter_key, term, limit):
        self.check_source_access()
        if filter_key not in self.relation_filters and filter_key != "search":
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
        if filter_key == "search":
            if not term:
                return []
            products = self.env["product.product"].search([
                "|", ("display_name", "ilike", term), ("default_code", "ilike", term),
            ], limit=limit)
            return [{"id": product.id, "label": product.display_name} for product in products]
        model_name, domain = self.relation_filters[filter_key]
        model = self.env[model_name]
        if not model.has_access("read"):
            return []
        options = model.name_search(name=term, domain=domain, operator="ilike", limit=limit)
        return [{"id": record_id, "label": label} for record_id, label in options]


class OrmSearchReportMixin:
    """Shared get_page/export_rows/search_filter_options for reports backed directly by an ORM
    domain + search_read/search_count - Move History, Internal Transfers. Each subclass only
    needs to implement _domain(filters)/_serialize(record)/_normalize_filters, and define
    field_names/sort_fields/relation_filters/default_sort.
    """

    def _order(self, sort):
        if not isinstance(sort, dict):
            raise ValidationError("Invalid report sort.")
        key = sort.get("key", self.default_sort["key"])
        direction = sort.get("direction", self.default_sort["direction"])
        if key not in self.sort_fields or direction not in ("asc", "desc"):
            raise ValidationError("Unsupported report sort.")
        return f"{self.sort_fields[key]} {direction}, id {direction}"

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

    # Override when the row_ids export path needs more than the standard location gate (e.g.
    # Internal Transfers also restricts to picking_type_code = "internal").
    def _export_restriction_domain(self):
        return self._location_restriction_domain()

    def export_rows(self, filters, sort, row_ids=None):
        self.check_source_access()
        if row_ids:
            rows = []
            batch_size = 1000
            restriction = self._export_restriction_domain()
            for offset in range(0, len(row_ids), batch_size):
                batch_ids = row_ids[offset:offset + batch_size]
                records = self.model.search_read([("id", "in", batch_ids)] + restriction, self.field_names)
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
