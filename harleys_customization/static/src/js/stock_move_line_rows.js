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
