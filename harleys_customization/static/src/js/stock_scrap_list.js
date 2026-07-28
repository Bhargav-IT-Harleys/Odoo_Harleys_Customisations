import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

/**
 * Inv Adjustments (stock.scrap): a Done row has every field readonly
 * already, so inline-editing it is a no-op - but core's base
 * isInlineEditable() only looks at the list-wide "editable" prop, not the
 * specific record (confirmed in list_renderer.js: it takes `_record` and
 * ignores it), so clicking a Done row still entered edit mode with
 * pointless Save/Discard chrome instead of just opening the record.
 * Overriding this per-record - combined with the list's own editable flag,
 * not instead of it - falls through to the renderer's existing
 * "not inline editable -> open the form" branch (onCellClicked), so a
 * Done row now behaves exactly like a normal read-only list row.
 */
export class StockScrapListRenderer extends ListRenderer {
    isInlineEditable(record) {
        return super.isInlineEditable(record) && record.data.state !== "done";
    }
}

export const stockScrapListView = {
    ...listView,
    Renderer: StockScrapListRenderer,
};

registry.category("views").add("stock_scrap_list", stockScrapListView);
