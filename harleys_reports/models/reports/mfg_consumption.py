from collections import defaultdict
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, ValidationError

from .base import PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin
from .date_utils import date_boundary
from .registry import register_report

_DEFAULT_WINDOW_DAYS = 7
_VARIANCE_MATCH_TOLERANCE = 0.01  # 1% of Required, below which a variance counts as a Match.
_SOURCE_MODELS = (
    "mrp.production", "mrp.bom", "stock.move", "stock.scrap", "product.product",
    "product.category", "stock.warehouse", "stock.picking.type",
)
# Selectable Production Centers are restricted to warehouses whose name contains this - not a
# formal Odoo concept, just this business's naming convention for manufacturing locations.
_PRODUCTION_CENTER_NAME_FILTER = "Production"
# Row id = warehouse_id * _WAREHOUSE_ID_MULTIPLIER + product_id * _PRODUCT_ID_MULTIPLIER +
# material_id. Must stay a plain int, not a composite string: the export controller's
# "export selected rows" path does int(row_id) on every id the client sends back (see
# controllers/export.py), matching the multiplier convention already used by
# in_transit_reconciliation.py/expiry_report.py. 10**7 comfortably exceeds any realistic
# product/warehouse id in this database.
_PRODUCT_ID_MULTIPLIER = 10**7
_WAREHOUSE_ID_MULTIPLIER = 10**14

_STATUS_OPTIONS = (
    {"value": "match", "label": "Match"},
    {"value": "over", "label": "Over"},
    {"value": "under", "label": "Under"},
    {"value": "unexpected", "label": "Unexpected"},
)


@register_report
class MfgConsumptionReport(SqlRowsReportMixin, ReportProvider):
    key = "mfg_consumption"
    title = "Mfg Consumption Report"
    description = (
        "For every top-level Manufacturing Order completed in the selected window, compares "
        "each material's flattened BoM requirement (scaled by actual output including scrap) "
        "against what was actually issued, valued at standard cost."
    )
    model_name = "mrp.production"

    filters = (
        # required_for_search: True on all three - the frontend's canSearch gate (see
        # reports_app.js) will not auto-run the report until every one of them has a value,
        # matching the same mechanism (and starts-empty behavior) already used by warehouse_ids
        # on physical_inventory.py/in_transit_reconciliation.py/expiry_report.py, just applied to
        # three filters here (canSearch is a plain .every() over every gated filter) instead of
        # one. Left optional server-side in _normalize_filters below, matching how those other
        # reports also only enforce this in the UI, not the API.
        {"key": "production_center_ids", "label": "Production Centers", "type": "multi_relation",
         "group": "primary", "required_for_search": True},
        {"key": "date_from", "label": "Mfg Date From", "type": "date", "group": "primary"},
        {"key": "date_to", "label": "Mfg Date To", "type": "date", "group": "primary"},
        PRODUCT_SEARCH_FILTER,
        {"key": "category_ids", "label": "Product Category", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        {"key": "production_section_ids", "label": "Production Section", "type": "multi_relation",
         "group": "primary", "required_for_search": True},
    )
    # A column's position in the table follows this declaration order exactly - the OWL app's
    # displayColumns getter filters this list in place rather than appending toggled-on optional
    # columns to the end, so each optional column is declared next to the required column it's
    # most related to instead of being bunched up at the tail.
    columns = (
        {"key": "production_center", "label": "Production Center", "type": "text", "sortable": True},
        {"key": "product_name", "label": "Product Name", "type": "text", "sortable": True},
        {"key": "fg_internal_reference", "label": "FG Internal Reference", "type": "text", "sortable": True,
         "optional": True},
        {"key": "fg_category", "label": "FG Product Category", "type": "text", "sortable": True, "optional": True},
        {"key": "production_section", "label": "Production Section", "type": "text", "sortable": True,
         "optional": True},
        {"key": "component", "label": "Material", "type": "text", "sortable": True},
        {"key": "material_internal_reference", "label": "Material Internal Reference", "type": "text",
         "sortable": True, "optional": True},
        {"key": "material_uom", "label": "Material UOM", "type": "text", "sortable": True},
        {"key": "required", "label": "Required", "type": "float", "sortable": True, "align": "end"},
        {"key": "actual", "label": "Actual", "type": "float", "sortable": True, "align": "end"},
        {"key": "scrap", "label": "Scrap", "type": "float", "sortable": True, "align": "end", "optional": True},
        {"key": "variance", "label": "Variance", "type": "float", "sortable": True, "align": "end"},
        {"key": "variance_pct", "label": "Variance %", "type": "float", "sortable": True, "align": "end"},
        # Label gets the company currency appended dynamically in metadata().
        {"key": "variance_value", "label": "Variance Value", "type": "float", "sortable": True, "align": "end"},
        {"key": "status", "label": "Status", "type": "badge", "sortable": True, "options": list(_STATUS_OPTIONS)},
    )
    relation_filters = {
        "category_ids": PRODUCT_RELATION_FILTERS["category_ids"],
        "production_section_ids": ("production.section", []),
    }
    default_sort = {"key": "production_center", "direction": "asc"}
    export_row_limit_hint = "Mfg date range"
    sort_fields = {
        "production_center": "production_center", "product_name": "product_name", "component": "component",
        "material_uom": "material_uom", "required": "required", "actual": "actual", "scrap": "scrap",
        "variance": "variance", "variance_pct": "variance_pct", "variance_value": "variance_value", "status": "status",
        "fg_internal_reference": "fg_internal_reference",
        "material_internal_reference": "material_internal_reference",
        "fg_category": "fg_category", "production_section": "production_section",
    }

    def check_source_access(self):
        for model_name in _SOURCE_MODELS:
            if not self.env[model_name].has_access("read"):
                raise AccessError(f"You do not have read access to {self.title} data.")

    def metadata(self):
        today = fields.Date.context_today(self.model)
        default_filters = {
            "date_from": fields.Date.to_string(today - timedelta(days=_DEFAULT_WINDOW_DAYS)),
            "date_to": fields.Date.to_string(today),
        }
        columns = [dict(column) for column in self.columns]
        currency = self.env.company.currency_id
        for column in columns:
            if column["key"] == "variance_value":
                column["label"] = f"Variance Value ({currency.symbol or currency.name})"
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": columns,
            "default_filters": default_filters,
            "default_sort": self.default_sort,
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
            "export_formats": ["csv", "xlsx"],
            "sidebar_note": (
                "No results load until Production Centers, Product Category, and Production "
                "Section all have at least one selection - pick a value in each and click Apply "
                "Filters. One row per Production Center + Product + Material, aggregated across every "
                "qualifying Manufacturing Order. \"Qualifying\" means: Source does not reference "
                "another MO (excludes auto-generated child/sub-assembly MOs - a Sales-Order-driven "
                "chain is a known exception this rule does not catch, since Odoo propagates the SO "
                "reference rather than the parent MO's name through such chains), state is Done, "
                "and the completion date/time falls in the selected window. Required scales off "
                "each MO's actual output including its own scrapped finished goods, not the "
                "originally planned quantity. Actual is done raw-material consumption plus "
                "raw-material scrap; the optional Scrap column breaks that scrap portion out on "
                "its own without changing what Actual includes. Variance Value is the quantity variance priced at standard "
                "cost. Production Centers only lists warehouses named with "
                f"\"{_PRODUCTION_CENTER_NAME_FILTER}\"."
            ),
        }

    def _normalize_filters(self, values):
        if not isinstance(values, dict):
            raise ValidationError("Invalid report filters.")
        allowed = {item["key"] for item in self.filters}
        if set(values) - allowed:
            raise ValidationError("Unsupported report filter.")
        if not values.get("date_from") or not values.get("date_to"):
            raise ValidationError("Select a date range.")
        normalized = {"date_from": values["date_from"], "date_to": values["date_to"]}
        for key, label in (
            ("production_center_ids", "production center"),
            ("category_ids", "category"),
            ("production_section_ids", "production section"),
        ):
            value = values.get(key)
            if value:
                normalized[key] = self._validate_id_list(value, label)
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        return normalized

    def search_filter_options(self, filter_key, term, limit):
        if filter_key != "production_center_ids":
            return super().search_filter_options(filter_key, term, limit)
        # Special-cased rather than declared in relation_filters: SqlRowsReportMixin's own
        # search_filter_options hardcodes "any stock.warehouse-typed filter" to
        # _allowed_warehouses(), which would silently ignore a name-restricting domain declared
        # in relation_filters and show every warehouse the user can access.
        self.check_source_access()
        if not isinstance(term, str) or len(term) > 100:
            raise ValidationError("Invalid filter search.")
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValidationError("Invalid filter option limit.")
        limit = max(1, min(limit, 200))
        domain = [("name", "ilike", _PRODUCTION_CENTER_NAME_FILTER)]
        if term:
            domain.append(("name", "ilike", term))
        warehouses = self.env["stock.warehouse"].search(domain, order="name", limit=limit)
        return [{"id": warehouse.id, "label": warehouse.name} for warehouse in warehouses]

    # -- BoM flattening (unchanged from the Transfer-based design) ---------------------------

    def _product_uom(self, product_id, uom_cache):
        if product_id not in uom_cache:
            uom_cache[product_id] = self.env["product.product"].browse(product_id).uom_id
        return uom_cache[product_id]

    def _convert_to_product_uom(self, qty, source_uom_id, product_id, uom_cache):
        if not qty:
            return 0.0
        target_uom = self._product_uom(product_id, uom_cache)
        if source_uom_id == target_uom.id:
            return qty
        return self.env["uom.uom"].browse(source_uom_id)._compute_quantity(qty, target_uom, round=False)

    def _resolve_child_boms(self, products):
        """Product -> its own mrp.bom, mirroring mrp.bom._bom_find's product/template matching
        (a product-specific BoM wins over a template-level one, first by sequence) but WITHOUT
        _bom_find_domain's hardcoded ('active', '=', True) clause - that clause is a literal
        domain term, not the implicit active_test context, so with_context(active_test=False)
        cannot bypass it. This module's own approval workflow (see the active_bom_ids comment in
        _flatten_bom above) means an unapproved sub-BoM must still be found here.
        """
        if not products:
            return {}
        domain = [
            "|",
            ("product_id", "in", products.ids),
            "&", ("product_id", "=", False), ("product_tmpl_id", "in", products.product_tmpl_id.ids),
        ]
        boms = self.env["mrp.bom"].with_context(active_test=False).search(domain, order="sequence, product_id, id")
        by_product, by_template = {}, {}
        for bom in boms:
            if bom.product_id:
                by_product.setdefault(bom.product_id, bom)
            else:
                by_template.setdefault(bom.product_tmpl_id, bom)
        return {
            product: by_product.get(product) or by_template.get(product.product_tmpl_id)
            for product in products
            if product in by_product or product.product_tmpl_id in by_template
        }

    def _flatten_bom(self, bom, cache, uom_cache, active_bom_ids=frozenset()):
        """Component product id -> quantity required per ONE unit of `bom`'s own product,
        converted into each component's own default UoM. Memoized by bom.id in `cache` so a
        BoM shared by many MOs is only ever flattened once per report request.
        """
        if bom.id in cache:
            return cache[bom.id]
        if bom.id in active_bom_ids:
            # A BoM cycle in this branch - stop here without caching, mirroring the per-branch
            # active_nodes guard in BOM_Exploder5.py's explode_bom_raw_only.
            return {}
        batch_qty = bom.product_qty or 1.0
        lines = bom.bom_line_ids
        # harleys_customization forces every newly created mrp.bom to active=False until it
        # clears an approval workflow (see MrpBom.create()/action_approve in
        # harleys_customization/models/mrp_bom.py) - resolving sub-BoMs with the standard
        # _bom_find would silently treat an unapproved semi-finished component's BoM as "no
        # BoM" (a leaf), understating the flattened requirement. _resolve_child_boms is batched
        # across every line's product in one call, like _bom_find, but doesn't filter on active.
        child_bom_by_product = self._resolve_child_boms(lines.mapped("product_id"))
        result = defaultdict(float)
        for line in lines:
            if not line.product_id or line.product_qty <= 0:
                continue
            factor = line.product_qty / batch_qty
            child_bom = child_bom_by_product.get(line.product_id)
            if child_bom:
                nested = self._flatten_bom(child_bom, cache, uom_cache, active_bom_ids | {bom.id})
                for product_id, qty in nested.items():
                    result[product_id] += qty * factor
            else:
                own_uom_qty = self._convert_to_product_uom(
                    line.product_qty, line.product_uom_id.id, line.product_id.id, uom_cache
                )
                result[line.product_id.id] += own_uom_qty / batch_qty
        cache[bom.id] = dict(result)
        return cache[bom.id]

    # -- Actual consumption (unchanged from the Transfer-based design) -----------------------

    def _consumption_by_mo_product(self, mo_ids, uom_cache):
        totals = defaultdict(float)
        if not mo_ids:
            return totals
        # scrap_id = False excludes raw-material-side scrap moves - a scrap's own underlying
        # move also carries raw_material_production_id (see mrp/models/stock_scrap.py's
        # _prepare_move_values), so without this exclusion every scrapped quantity would be
        # double-counted here AND in _scrap_by_mo_product below.
        moves = self.env["stock.move"].search_read(
            [("raw_material_production_id", "in", mo_ids), ("state", "=", "done"), ("scrap_id", "=", False)],
            ["raw_material_production_id", "product_id", "product_uom", "quantity"],
        )
        for move in moves:
            product_id = move["product_id"][0]
            mo_id = move["raw_material_production_id"][0]
            qty = self._convert_to_product_uom(move["quantity"], move["product_uom"][0], product_id, uom_cache)
            totals[(mo_id, product_id)] += qty
        return totals

    def _scrap_by_mo_product(self, mo_ids, uom_cache):
        totals = defaultdict(float)
        if not mo_ids:
            return totals
        # move_ids.raw_material_production_id (rather than plain production_id) is what
        # distinguishes component/raw-material scrap from finished-goods scrap - both can carry
        # the same production_id, see mrp/models/stock_scrap.py's _prepare_move_values.
        scraps = self.env["stock.scrap"].search_read(
            [
                ("production_id", "in", mo_ids),
                ("state", "=", "done"),
                ("move_ids.raw_material_production_id", "!=", False),
            ],
            ["production_id", "product_id", "product_uom_id", "scrap_qty"],
        )
        for scrap in scraps:
            product_id = scrap["product_id"][0]
            mo_id = scrap["production_id"][0]
            qty = self._convert_to_product_uom(scrap["scrap_qty"], scrap["product_uom_id"][0], product_id, uom_cache)
            totals[(mo_id, product_id)] += qty
        return totals

    # -- Row construction ----------------------------------------------------------------------

    def _classify(self, required, actual):
        if not required:
            return "unexpected"
        diff = actual - required
        if abs(diff) <= _VARIANCE_MATCH_TOLERANCE * abs(required):
            return "match"
        return "over" if diff > 0 else "under"

    def _extended_product_display(self, product_id, cache):
        if product_id not in cache:
            product = self.env["product.product"].browse(product_id)
            category = product.categ_id.display_name.rsplit(" / ", 1)[-1] if product.categ_id else ""
            cache[product_id] = {
                "name": product.display_name,
                "uom": product.uom_id.name,
                "internal_reference": product.default_code or "",
                "category": category,
            }
        return cache[product_id]

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        date_from = date_boundary(self.env, values["date_from"])
        date_to = date_boundary(self.env, values["date_to"], end=True)

        # 'not like' excludes auto-generated child/sub-assembly MOs, whose origin is set to the
        # parent MO's own name (e.g. "WH/MO/00123") - see mrp/models/mrp_production.py
        # _get_origin(). Known, accepted gap: a Sales-Order-driven chain propagates the SO's own
        # reference through every descendant MO instead, so a child MO there would not contain
        # "/MO/" either and would incorrectly pass this filter - documented, not worked around.
        domain = [
            ("origin", "not like", "/MO/"),
            ("state", "=", "done"),
            ("date_finished", ">=", date_from),
            ("date_finished", "<", date_to),
        ]
        if values.get("production_section_ids"):
            domain.append(("section", "in", values["production_section_ids"]))
        if values.get("production_center_ids"):
            domain.append(("picking_type_id.warehouse_id", "in", values["production_center_ids"]))
        if values.get("category_ids"):
            domain.append(("product_id.categ_id", "child_of", values["category_ids"]))
        if values.get("search"):
            domain += [
                "|", ("product_id.display_name", "ilike", values["search"]),
                ("product_id.default_code", "ilike", values["search"]),
            ]

        mos = self.env["mrp.production"].search_read(
            domain, ["product_id", "qty_produced", "bom_id", "section", "picking_type_id"],
        )
        if not mos:
            return []
        mo_ids = [mo["id"] for mo in mos]

        # Production Center = the MO's own operation type's warehouse - batched in one lookup
        # rather than resolved per MO.
        picking_type_ids = list({mo["picking_type_id"][0] for mo in mos if mo["picking_type_id"]})
        warehouse_by_picking_type = {}
        if picking_type_ids:
            for picking_type in self.env["stock.picking.type"].search_read(
                [("id", "in", picking_type_ids)], ["warehouse_id"]
            ):
                warehouse_by_picking_type[picking_type["id"]] = picking_type["warehouse_id"]

        def mo_center(mo):
            picking_type = mo["picking_type_id"]
            warehouse = warehouse_by_picking_type.get(picking_type[0]) if picking_type else None
            return (warehouse[0], warehouse[1]) if warehouse else (0, "No Production Center")

        center_by_mo = {mo["id"]: mo_center(mo) for mo in mos}
        product_by_mo = {mo["id"]: mo["product_id"][0] for mo in mos}

        uom_cache = {}
        bom_cache = {}
        flattened_by_bom = {}
        for mo in mos:
            bom_id = mo["bom_id"][0] if mo["bom_id"] else None
            if bom_id and bom_id not in flattened_by_bom:
                flattened_by_bom[bom_id] = self._flatten_bom(
                    self.env["mrp.bom"].browse(bom_id), bom_cache, uom_cache
                )

        # Required, grouped by (Production Center, Finished Product, Material). qty_produced
        # already includes any of the MO's own output later scrapped - verified empirically:
        # scrapping a finished-good product creates another stock.move under move_finished_ids
        # for that same product (see mrp/models/stock_scrap.py _prepare_move_values), and
        # mrp.production._get_produced_qty sums every done+picked move_finished_ids move for the
        # MO's own product without excluding scrap-linked ones. Adding a separate finished-goods
        # scrap figure on top of qty_produced would double count it.
        required_by_key = defaultdict(float)
        for mo in mos:
            bom_id = mo["bom_id"][0] if mo["bom_id"] else None
            per_unit = flattened_by_bom.get(bom_id, {})
            total_qty = mo["qty_produced"] or 0.0
            warehouse_id, warehouse_name = center_by_mo[mo["id"]]
            product_id = product_by_mo[mo["id"]]
            for material_id, qty in per_unit.items():
                required_by_key[(warehouse_id, warehouse_name, product_id, material_id)] += qty * total_qty

        # Kept separate (not merged) so raw-material scrap can be shown as its own optional
        # column, in addition to still being folded into Actual below.
        consumption = self._consumption_by_mo_product(mo_ids, uom_cache)
        scrap = self._scrap_by_mo_product(mo_ids, uom_cache)
        actual_by_key = defaultdict(float)
        scrap_by_key = defaultdict(float)
        for (mo_id, material_id), qty in consumption.items():
            warehouse_id, warehouse_name = center_by_mo[mo_id]
            product_id = product_by_mo[mo_id]
            actual_by_key[(warehouse_id, warehouse_name, product_id, material_id)] += qty
        for (mo_id, material_id), qty in scrap.items():
            warehouse_id, warehouse_name = center_by_mo[mo_id]
            product_id = product_by_mo[mo_id]
            actual_by_key[(warehouse_id, warehouse_name, product_id, material_id)] += qty
            scrap_by_key[(warehouse_id, warehouse_name, product_id, material_id)] += qty

        all_keys = set(required_by_key) | set(actual_by_key)
        if not all_keys:
            return []
        material_ids = {key[3] for key in all_keys}

        cost_cache = {}
        cost_by_product = self._company_scoped_products(
            cost_cache, self.env.company.id, list(material_ids), ("standard_price",)
        )

        # section is a related field off the finished product's own template, so it's constant
        # per product_id regardless of which MO it came from - no need for a fresh query.
        section_by_product = {mo["product_id"][0]: mo["section"] for mo in mos}

        product_cache = {}
        rows = []
        for warehouse_id, warehouse_name, product_id, material_id in all_keys:
            key = (warehouse_id, warehouse_name, product_id, material_id)
            required = required_by_key.get(key, 0.0)
            actual = actual_by_key.get(key, 0.0)
            scrap_qty = scrap_by_key.get(key, 0.0)
            variance = actual - required
            variance_pct = (variance / required) * 100 if required else None
            unit_cost = cost_by_product.get(material_id, {}).get("standard_price") or 0.0
            variance_value = variance * unit_cost

            material = self._extended_product_display(material_id, product_cache)
            finished = self._extended_product_display(product_id, product_cache)

            rows.append({
                "id": warehouse_id * _WAREHOUSE_ID_MULTIPLIER + product_id * _PRODUCT_ID_MULTIPLIER + material_id,
                "production_center": warehouse_name,
                "product_name": finished["name"],
                "component": material["name"],
                "material_uom": material["uom"],
                "required": round(required, 4),
                "actual": round(actual, 4),
                "scrap": round(scrap_qty, 4),
                "variance": round(variance, 4),
                "variance_pct": round(variance_pct, 2) if variance_pct is not None else None,
                "variance_value": round(variance_value, 2),
                "status": self._classify(required, actual),
                "fg_internal_reference": finished["internal_reference"],
                "material_internal_reference": material["internal_reference"],
                "fg_category": finished["category"],
                "production_section": self._display(section_by_product.get(product_id)),
            })
        return rows
