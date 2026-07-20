import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getMoveLineRows } from "./stock_move_line_rows";

/**
 * Editable per-batch quantity column for the Operations grid (Internal
 * Transfers). Renders one row per entry in the shared rows dataset
 * (stock_move_line_rows.js) - the same dataset the Batch column renders -
 * writing directly to the underlying stock.move.line's quantity field.
 * No intermediate/summary field, no separate synchronization logic.
 * Odoo's own compute on stock.move.quantity ("Qty Received") already
 * depends on move_line_ids.quantity, so it updates on its own once the
 * form is saved.
 */
export class StockMoveLineQtyEditor extends Component {
    static template = "harleys_customization.StockMoveLineQtyEditor";
    static props = { ...standardFieldProps };

    get rows() {
        return getMoveLineRows(this.props.record);
    }

    onQuantityChange(line, ev) {
        const value = parseFloat(ev.target.value);
        line.update({ quantity: Number.isNaN(value) ? 0 : value });
    }
}

export const stockMoveLineQtyEditor = {
    component: StockMoveLineQtyEditor,
};

registry.category("fields").add("stock_move_line_qty_editor", stockMoveLineQtyEditor);
