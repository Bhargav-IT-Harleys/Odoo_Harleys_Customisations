from collections import defaultdict

from odoo.exceptions import ValidationError

from .base import (
    PRODUCT_DISPLAY_FIELDS, PRODUCT_RELATION_FILTERS, PRODUCT_SEARCH_FILTER, ReportProvider, SqlRowsReportMixin,
)
from .date_utils import date_boundary, to_local_string
from .registry import register_report

# Row id = move_id * _MOVE_ID_MULTIPLIER + lot_id. A single stock.move can produce more than one
# sent-leg row here only when it carries more than one lot, so lot_id is enough to disambiguate.
_MOVE_ID_MULTIPLIER = 1_000_000

_STATUS_OPTIONS = (
    {"value": "not_received", "label": "Not Received"},
    {"value": "partially_received", "label": "Partially Received"},
    {"value": "short_receipt", "label": "Short Receipt"},
    {"value": "excess_receipt", "label": "Excess Receipt"},
    {"value": "likely_misdirected", "label": "Likely Misdirected"},
    {"value": "matched", "label": "Matched"},
    {"value": "fully_received", "label": "Fully Received"},
)
# Shown by default (resolution_visibility="unresolved") - everything except the two "this is
# genuinely done, nothing to review" outcomes. matched/fully_received are functionally the same
# idea (received == sent) but kept as distinct statuses since one carries a confirmed link and
# the other doesn't - see the Link column.
_RESOLVED_STATUSES = {"matched", "fully_received"}
_LINK_OPTIONS = (
    {"value": "confirmed", "label": "Confirmed"},
    {"value": "pending", "label": "Pending"},
    {"value": "unlinked", "label": "Unlinked"},
)


@register_report
class InTransitReconciliationReport(SqlRowsReportMixin, ReportProvider):
    key = "in_transit_reconciliation"
    title = "In-Transit Reconciliation"
    description = "For every dispatch into transit, whether it has actually been received out the other side."
    model_name = "stock.move.line"

    filters = (
        PRODUCT_SEARCH_FILTER,
        {"key": "warehouse_ids", "label": "Warehouses", "type": "multi_relation", "group": "primary",
         "required_for_search": True},
        {"key": "date_from", "label": "Sent Date From", "type": "date", "group": "primary"},
        {"key": "date_to", "label": "Sent Date To", "type": "date", "group": "primary"},
        {"key": "category_ids", "label": "Product Categories", "type": "multi_relation", "group": "advanced"},
        # No blank "All" state - a row is always either "still needs review" or "resolved", one
        # of the two must apply. Mirrors Stock Report's adu_visibility exactly.
        {"key": "resolution_visibility", "label": "Resolution Visibility", "type": "selection", "group": "advanced",
         "required": True,
         "options": [
             {"value": "unresolved", "label": "Unresolved Only"},
             {"value": "all", "label": "Show All"},
         ]},
    )
    columns = (
        {"key": "dispatch_reference", "label": "Dispatch Reference", "type": "text", "sortable": True},
        {"key": "source_location", "label": "Source Location", "type": "text", "sortable": True},
        {"key": "transit_location", "label": "Transit Location", "type": "text", "sortable": True},
        {"key": "destination_location", "label": "Destination", "type": "text", "sortable": True},
        {"key": "sku", "label": "Product Code", "type": "text", "sortable": True, "optional": True},
        {"key": "product", "label": "Product", "type": "text", "sortable": True, "filter_key": "search"},
        {"key": "category", "label": "Product Category", "type": "text", "sortable": True, "filter_key": "category_ids"},
        {"key": "lot", "label": "Lot", "type": "text", "sortable": True},
        {"key": "uom", "label": "UOM", "type": "text", "sortable": True},
        {"key": "contact", "label": "Contact", "type": "text", "sortable": True, "optional": True},
        {"key": "sent_date", "label": "Sent Date", "type": "datetime", "sortable": True},
        {"key": "sent_quantity", "label": "Sent Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "received_quantity", "label": "Received Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "pending_quantity", "label": "Pending Qty", "type": "float", "sortable": True, "align": "end"},
        {"key": "link", "label": "Link", "type": "badge", "sortable": True, "options": list(_LINK_OPTIONS)},
        {"key": "status", "label": "Status", "type": "badge", "sortable": True, "options": list(_STATUS_OPTIONS)},
    )
    relation_filters = PRODUCT_RELATION_FILTERS
    default_sort = {"key": "sent_date", "direction": "desc"}
    sort_fields = {
        "dispatch_reference": "dispatch_reference", "source_location": "source_location",
        "transit_location": "transit_location", "destination_location": "destination_location",
        "sku": "sku", "product": "product", "category": "category", "lot": "lot", "uom": "uom",
        "contact": "contact",
        "sent_date": "sent_date", "sent_quantity": "sent_quantity", "received_quantity": "received_quantity",
        "pending_quantity": "pending_quantity", "link": "link", "status": "status",
    }
    allowed_resolution_visibility = ("unresolved", "all")

    def metadata(self):
        return {
            **self.summary(),
            "filters": [dict(item) for item in self.filters],
            "columns": [dict(column) for column in self.columns],
            "default_filters": {"resolution_visibility": "unresolved", **self._default_category_filter()},
            "default_sort": self.default_sort,
            "page_sizes": list(self.page_sizes),
            "default_page_size": self.default_page_size,
            "maximum_page_size": self.maximum_page_size,
            "export_formats": ["csv", "xlsx"],
            "sidebar_note": (
                "Unresolved Only (default) hides Matched and Fully Received rows. Link shows "
                "\"Confirmed\" once the linked receipt is actually done, \"Pending\" when Odoo "
                "knows where it's headed but that receipt is still open (Destination is shown "
                "either way), and \"Unlinked\" when there's no Odoo record tying it to a specific "
                "receipt at all, so Destination is blank and Received/Pending is an estimate. "
                "\"Likely Misdirected\" means this dispatch's own linked receipt is still open, "
                "but something else has already left the same transit location for this "
                "product/lot - worth checking who actually received it. Sent Date and Warehouses "
                "are optional - leave them blank to see every dispatch."
            ),
        }

    def _normalize_filters(self, values):
        if not isinstance(values, dict):
            raise ValidationError("Invalid report filters.")
        allowed = {item["key"] for item in self.filters}
        if set(values) - allowed:
            raise ValidationError("Unsupported report filter.")
        normalized = {}
        warehouse_ids = values.get("warehouse_ids")
        if warehouse_ids:
            normalized["warehouse_ids"] = self._validate_id_list(warehouse_ids, "warehouse")
        category_ids = values.get("category_ids")
        if category_ids:
            normalized["category_ids"] = self._validate_id_list(category_ids, "category")
        if values.get("date_from"):
            normalized["date_from"] = values["date_from"]
        if values.get("date_to"):
            normalized["date_to"] = values["date_to"]
        search_term = values.get("search")
        if search_term:
            if not isinstance(search_term, str) or len(search_term) > 100:
                raise ValidationError("Invalid search term.")
            normalized["search"] = search_term.strip()
        resolution_visibility = values.get("resolution_visibility")
        normalized["resolution_visibility"] = (
            resolution_visibility if resolution_visibility in self.allowed_resolution_visibility else "unresolved"
        )
        return normalized

    def _build_rows(self, filters):
        values = self._normalize_filters(filters)
        category_ids = values.get("category_ids")
        search_term = values.get("search")
        companies = self.env.companies.ids
        allowed_location_ids = self._allowed_location_ids()

        # Optional narrowing on top of the access restriction above - unset means "every
        # warehouse I'm allowed into", not "none".
        warehouse_location_ids = None
        if values.get("warehouse_ids"):
            warehouse_location_ids = set()
            for warehouse in self._resolve_warehouses(values["warehouse_ids"]):
                warehouse_location_ids.update(self._warehouse_location_ids(warehouse))

        # Sent Date is an optional display narrowing applied after the fact - the cum_sent/
        # quant_balance computation below must keep replaying full history regardless, or the
        # FIFO/pool-balance math for Tier 3 would be wrong near the window edges.
        date_from = date_boundary(self.env, values["date_from"]) if values.get("date_from") else None
        date_to = date_boundary(self.env, values["date_to"], end=True) if values.get("date_to") else None

        # Running per-(transit, product, lot) cumulative-sent total ordered by date - the FIFO
        # axis used below for unlinked dispatches (Tier 3). Company-scoped via the move itself,
        # not the location, since a shared transit location's own company_id can be unset.
        self.env.cr.execute("""
            WITH sent_legs AS (
                SELECT sm.id AS move_id, sm.picking_id, sml.location_id AS source_location_id,
                       sml.location_dest_id AS transit_id, sml.product_id, sml.lot_id,
                       COALESCE(sml.lot_id, 0) AS lot_key,
                       SUM(sml.quantity) AS quantity, MAX(sml.date) AS sent_date
                FROM stock_move sm
                JOIN stock_move_line sml ON sml.move_id = sm.id
                JOIN stock_location transit ON transit.id = sml.location_dest_id
                WHERE sm.state = 'done' AND transit.usage = 'transit' AND sm.company_id = ANY(%(companies)s)
                GROUP BY sm.id, sm.picking_id, sml.location_id, sml.location_dest_id, sml.product_id, sml.lot_id
            )
            SELECT move_id, picking_id, source_location_id, transit_id, product_id, lot_id, lot_key,
                   quantity, sent_date,
                   SUM(quantity) OVER (PARTITION BY transit_id, product_id, lot_key ORDER BY sent_date, move_id
                                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_sent
            FROM sent_legs
        """, {"companies": companies})
        sent_rows = self.env.cr.fetchall()
        if not sent_rows:
            return []

        # Final cumulative-sent total per (transit, product, lot) group - a separate aggregate,
        # not derived from row order in Python, since fetchall() order isn't guaranteed to match
        # the window's PARTITION order.
        self.env.cr.execute("""
            SELECT sml.location_dest_id, sml.product_id, COALESCE(sml.lot_id, 0), SUM(sml.quantity)
            FROM stock_move_line sml
            JOIN stock_move sm ON sm.id = sml.move_id
            JOIN stock_location transit ON transit.id = sml.location_dest_id
            WHERE sm.state = 'done' AND transit.usage = 'transit' AND sm.company_id = ANY(%(companies)s)
            GROUP BY sml.location_dest_id, sml.product_id, COALESCE(sml.lot_id, 0)
        """, {"companies": companies})
        cum_sent_total_map = {(t, p, l): qty or 0.0 for t, p, l, qty in self.env.cr.fetchall()}

        # Live stock_quant balance per group - authoritative over a replayed move ledger, which
        # can drift. No company filter here: stock_quant.company_id is NULL on ~99% of transit
        # rows (shared hubs, unlike stock_move.company_id above which is reliably populated).
        self.env.cr.execute("""
            SELECT sq.location_id, sq.product_id, COALESCE(sq.lot_id, 0), SUM(sq.quantity)
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            WHERE sl.usage = 'transit'
            GROUP BY sq.location_id, sq.product_id, COALESCE(sq.lot_id, 0)
        """)
        quant_balance_map = {(t, p, l): qty or 0.0 for t, p, l, qty in self.env.cr.fetchall()}

        # Per-sent-move link info (Tier 1/2): every destination move stock_move_move_rel says
        # completes this dispatch, whatever its current state. Keyed by move id only, not lot -
        # the destination leg frequently records a *different* lot than the one dispatched (~10%
        # of linked+done pairs relabel on receipt), so an exact lot match can't gate the link
        # itself. The per-lot breakdown (lot_key per line) is kept for the allocation pass below.
        self.env.cr.execute("""
            SELECT rel.move_orig_id, dest_move.id, dest_move.state, dest_move.location_dest_id,
                   COALESCE(dest_sml.lot_id, 0) AS lot_key,
                   COALESCE(dest_sml.quantity, 0)
            FROM stock_move_move_rel rel
            JOIN stock_move dest_move ON dest_move.id = rel.move_dest_id
            LEFT JOIN stock_move_line dest_sml ON dest_sml.move_id = dest_move.id AND dest_sml.state = 'done'
            WHERE dest_move.state != 'cancel'
        """)
        link_map = defaultdict(list)
        for sent_move_id, dest_move_id, dest_state, dest_location_id, lot_key, received_qty in self.env.cr.fetchall():
            link_map[sent_move_id].append({
                "dest_move_id": dest_move_id, "state": dest_state, "lot_key": lot_key,
                "destination_location_id": dest_location_id, "received_qty": received_qty,
            })

        # Group-level total that left through a completed linked receipt - used only for Tier 2's
        # "did something else drain this pool" check, not per-dispatch.
        self.env.cr.execute("""
            SELECT dest_sml.location_id, dest_sml.product_id, COALESCE(dest_sml.lot_id, 0), SUM(dest_sml.quantity)
            FROM stock_move_move_rel rel
            JOIN stock_move dest_move ON dest_move.id = rel.move_dest_id
            JOIN stock_move_line dest_sml ON dest_sml.move_id = dest_move.id
            WHERE dest_move.state = 'done'
            GROUP BY dest_sml.location_id, dest_sml.product_id, COALESCE(dest_sml.lot_id, 0)
        """)
        linked_done_total_map = {(t, p, l): qty or 0.0 for t, p, l, qty in self.env.cr.fetchall()}

        # Includes open (not-done) links too - Tier 2 rows show their intended-but-unconfirmed
        # destination as well (see the row-building loop below).
        destination_location_ids = {
            link["destination_location_id"]
            for links in link_map.values() for link in links
            if link["destination_location_id"]
        }
        all_location_ids = {row[2] for row in sent_rows} | {row[3] for row in sent_rows} | destination_location_ids
        # sudo() for read-only display labels: the row-level access filter below already decides
        # whether this user can see a given dispatch, but a visible row's *other* end can still
        # sit in a different company (e.g. a TG dispatch headed to Mumbai), which browse() alone
        # would refuse to read.
        location_names = {
            location.id: location.complete_name
            for location in self.env["stock.location"].sudo().browse(all_location_ids)
        }
        pickings = self.env["stock.picking"].sudo().browse({row[1] for row in sent_rows if row[1]})
        picking_names = {picking.id: picking.name for picking in pickings}
        picking_contacts = {picking.id: picking.partner_id.name or "" for picking in pickings}
        lot_names = {
            lot.id: lot.name
            for lot in self.env["stock.lot"].sudo().browse({row[5] for row in sent_rows if row[5]})
        }
        product_ids_all = list({row[4] for row in sent_rows})
        allowed_product_ids = self._filter_product_ids(product_ids_all, category_ids, search_term)

        product_data = {
            product["id"]: product
            for product in self.env["product.product"].search_read(
                [("id", "in", product_ids_all)], list(PRODUCT_DISPLAY_FIELDS),
            )
        }

        # Move-level allocation for Tier 1 (linked + done): a lot that the destination recorded
        # under the exact same lot_id gets its exact quantity; any lot(s) left over (because the
        # destination relabeled them) share whatever's left of the destination's total, split
        # proportionally by how much of the move each of them sent. For the ~90% of pairs where
        # lots are preserved this reduces to an exact match; for the ~10% that get relabeled it's
        # the best attribution the data supports, rather than showing the move as unlinked.
        move_lot_quantities = defaultdict(dict)
        for row in sent_rows:
            move_lot_quantities[row[0]][row[6]] = row[7]

        move_allocation = {}
        for move_id, lot_quantities in move_lot_quantities.items():
            done_links = [link for link in link_map.get(move_id, []) if link["state"] == "done"]
            if not done_links:
                continue
            dest_by_lot = defaultdict(float)
            for link in done_links:
                dest_by_lot[link["lot_key"]] += link["received_qty"]
            dest_total = sum(dest_by_lot.values())
            default_destination = done_links[0]["destination_location_id"]

            exact_matched_total = 0.0
            unmatched_lot_keys = []
            for lot_key, sent_qty in lot_quantities.items():
                if lot_key in dest_by_lot:
                    move_allocation[(move_id, lot_key)] = {
                        "received_qty": dest_by_lot[lot_key], "destination_location_id": default_destination,
                    }
                    exact_matched_total += dest_by_lot[lot_key]
                else:
                    unmatched_lot_keys.append(lot_key)
            leftover = dest_total - exact_matched_total
            unmatched_sent_total = sum(lot_quantities[lk] for lk in unmatched_lot_keys)
            for lot_key in unmatched_lot_keys:
                received_qty = (leftover * (lot_quantities[lot_key] / unmatched_sent_total)) if unmatched_sent_total > 0 else 0.0
                move_allocation[(move_id, lot_key)] = {
                    "received_qty": received_qty, "destination_location_id": default_destination,
                }

        rows = []
        for (move_id, picking_id, source_location_id, transit_id, product_id, lot_id, lot_key,
             quantity, sent_date, cum_sent) in sent_rows:
            if product_id not in allowed_product_ids:
                continue
            if date_from and sent_date < date_from:
                continue
            if date_to and sent_date >= date_to:
                continue
            product = product_data.get(product_id)
            if not product:
                continue

            group_key = (transit_id, product_id, lot_key)
            links = link_map.get(move_id, [])
            done_links = [link for link in links if link["state"] == "done"]
            open_links = [link for link in links if link["state"] != "done"]

            if done_links:
                allocation = move_allocation[(move_id, lot_key)]
                received_quantity = allocation["received_qty"]
                destination_location_id = allocation["destination_location_id"]
                if abs(received_quantity - quantity) < 0.01:
                    status = "matched"
                elif received_quantity < quantity:
                    status = "short_receipt"
                else:
                    status = "excess_receipt"
                pending_quantity = max(0.0, quantity - received_quantity)
                link = "confirmed"
            elif open_links:
                cum_sent_total = cum_sent_total_map.get(group_key, 0.0)
                linked_done_total = linked_done_total_map.get(group_key, 0.0)
                current_balance = quant_balance_map.get(group_key, 0.0)
                expected_balance = cum_sent_total - linked_done_total
                status = "likely_misdirected" if expected_balance - current_balance > 0.01 else "not_received"
                received_quantity = 0.0
                pending_quantity = quantity
                # Not yet received (the linked move is still open), but the link tells us exactly
                # where it's headed - show that intended destination rather than leaving it blank.
                destination_location_id = open_links[0]["destination_location_id"]
                link = "pending"
            else:
                cum_sent_total = cum_sent_total_map.get(group_key, 0.0)
                current_balance = quant_balance_map.get(group_key, 0.0)
                pending_quantity = max(0.0, min(quantity,
                    cum_sent - max(cum_sent - quantity, cum_sent_total - current_balance)
                ))
                received_quantity = quantity - pending_quantity
                if pending_quantity <= 0.01:
                    status = "fully_received"
                elif pending_quantity >= quantity - 0.01:
                    status = "not_received"
                else:
                    status = "partially_received"
                destination_location_id = None
                link = "unlinked"

            if source_location_id not in allowed_location_ids and (
                destination_location_id is None or destination_location_id not in allowed_location_ids
            ):
                continue

            if warehouse_location_ids is not None and source_location_id not in warehouse_location_ids and (
                destination_location_id is None or destination_location_id not in warehouse_location_ids
            ):
                continue

            if values["resolution_visibility"] == "unresolved" and status in _RESOLVED_STATUSES:
                continue

            rows.append({
                "id": move_id * _MOVE_ID_MULTIPLIER + (lot_id or 0),
                "dispatch_reference": picking_names.get(picking_id, ""),
                "source_location": location_names.get(source_location_id, ""),
                "transit_location": location_names.get(transit_id, ""),
                "destination_location": location_names.get(destination_location_id, "") if destination_location_id else "",
                "contact": picking_contacts.get(picking_id, ""),
                "sku": product.get("default_code") or "",
                "product": self._display(product.get("product_tmpl_id")),
                "category": self._leaf_category(product),
                "lot": lot_names.get(lot_id, ""),
                "uom": self._display(product.get("uom_id")),
                "sent_date": to_local_string(self.env, sent_date),
                "sent_quantity": round(quantity, 2),
                "received_quantity": round(received_quantity, 2),
                "pending_quantity": round(pending_quantity, 2),
                "link": link,
                "status": status,
            })
        return rows
