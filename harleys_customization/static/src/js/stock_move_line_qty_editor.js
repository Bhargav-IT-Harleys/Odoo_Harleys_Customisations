import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getMoveLineRows } from "./stock_move_line_rows";

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
