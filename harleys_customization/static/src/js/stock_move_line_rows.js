/**
 * Single source of truth for "what batches/quantities are showing right
 * now, in what order" on an Internal Transfer's Operations grid. Both the
 * Batch and Batch Qty columns call this exact function against the same
 * stock.move record - there is one computation, not two, so the columns
 * cannot independently drift out of sync with each other.
 *
 * Row presence and order come from lot_ids.records - the same array
 * many2many_tags_field.js itself reads for its own display (see its
 * get tags(), which maps over record.data[name].records) - because that's
 * the one field that updates instantly/locally the moment a lot is added
 * or removed, before any server round-trip.
 *
 * Quantity comes from move_line_ids, when a matching line already exists.
 * A lot just added via this session has no line yet: Odoo's onchange
 * mechanism does not deliver a newly-created stock.move.line to the
 * client (confirmed by inspecting the actual onchange RPC response - the
 * server recomputes and returns "quantity" and the forecast fields, but
 * never move_line_ids itself), so line is null until the record is saved.
 * That is a hard, server-side limitation, not something any client-side
 * architecture can route around without an explicit extra save/read.
 */
export function getMoveLineRows(record) {
    const lineList = record.data.move_line_ids;
    const lotList = record.data.lot_ids;
    if (!lineList || !lotList) {
        return [];
    }
    const lineByLotId = new Map();
    for (const line of lineList.records) {
        if (line.data.lot_id) {
            lineByLotId.set(line.data.lot_id.id, line);
        }
    }
    return lotList.records.map((lot) => ({
        key: lot.resId ?? lot.id,
        lot,
        line: lineByLotId.get(lot.resId) || null,
    }));
}
