from odoo.exceptions import AccessError, ValidationError


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

    def __init__(self, env):
        self.env = env

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
