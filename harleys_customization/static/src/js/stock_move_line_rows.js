/**
 * Single source of truth for "what batches/quantities are showing right
 * now, in what order" on the Operations grid (Internal Transfers,
 * Receipts, Deliveries). Both the Batch and Batch Qty columns call this
 * exact function against the same stock.move record.
 *
 * Row presence/order primarily comes from lot_ids.records - the same
 * array many2many_tags_field.js itself reads for its own display -
 * because that's the one field that updates instantly/locally the
 * moment a lot is added or removed, before any server round-trip.
 *
 * One exception, needed for Receipts specifically: core's own
 * _compute_lot_ids domain excludes move lines with quantity == 0
 * (odoo/addons/stock/models/stock_move.py). harleys_customization
 * forces every newly-created line's quantity to 0 on incoming pickings
 * (stock_picking.py, _prepare_move_line_vals: "Override quantity to 0
 * for GRN") - so a lot just added there is immediately excluded from
 * lot_ids after the auto-save, even though its move line genuinely
 * exists. Left unhandled, the row vanishes before the user gets a
 * chance to type the real quantity. So: any move_line_ids entry whose
 * lot isn't present in lot_ids is also surfaced as its own row. These
 * rows have no `lot` (the lot was never part of the lot_ids relation
 * to begin with, so there's nothing to unlink there) - deletion for
 * them has to go through the line itself instead (see deleteLine in
 * stock_move_line_batch_field.js).
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
    const seenLotIds = new Set();
    const rows = lotList.records.map((lot) => {
        const id = lot.resId ?? lot.id;
        seenLotIds.add(id);
        return {
            key: id,
            lotId: id,
            lotName: lot.data.display_name,
            lot,
            line: lineByLotId.get(id) || null,
        };
    });
    for (const line of lineList.records) {
        const lotVal = line.data.lot_id;
        if (lotVal && !seenLotIds.has(lotVal.id)) {
            seenLotIds.add(lotVal.id);
            rows.push({
                key: `line-${line.id}`,
                lotId: lotVal.id,
                lotName: lotVal.display_name,
                lot: null,
                line,
            });
        }
    }
    return rows;
}
