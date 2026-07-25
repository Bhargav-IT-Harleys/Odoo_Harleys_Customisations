/**
 * Shared row list for the Batch/Batch Qty/Expiry Date columns on the
 * Operations grid, built from lot_ids.records so all three stay in sync.
 *
 * Receipts also surface move_line_ids entries not present in lot_ids:
 * core's _compute_lot_ids excludes quantity == 0 lines, and
 * harleys_customization forces new GRN lines to quantity 0
 * (stock_picking.py), so a just-added lot would otherwise vanish before
 * the user can type the real quantity. Those fallback rows have no
 * `lot` - deletion goes through the line instead (see deleteLine in
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
