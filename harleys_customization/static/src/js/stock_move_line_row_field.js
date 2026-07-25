import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { formatDate } from "@web/core/l10n/dates";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getMoveLineRows } from "./stock_move_line_rows";

/**
 * Generic "one value per batch row" column for the Operations grid - reused
 * for both Batch Qty (editable, numeric) and Expiry Date (read-only,
 * formatted date), configured per column via widget options in the view.
 */
export class StockMoveLineRowField extends Component {
    static template = "harleys_customization.StockMoveLineRowField";
    static props = {
        ...standardFieldProps,
        rowField: String,
        editable: { type: Boolean, optional: true },
        dateFormat: { type: String, optional: true },
    };
    static defaultProps = {
        editable: false,
    };

    get rows() {
        return getMoveLineRows(this.props.record);
    }

    getDisplayValue(row) {
        const value = row.line?.data[this.props.rowField];
        if (this.props.dateFormat) {
            return value ? formatDate(value, { format: this.props.dateFormat }) : "";
        }
        return value ?? "";
    }

    onValueChange(line, ev) {
        const value = parseFloat(ev.target.value);
        line.update({ [this.props.rowField]: Number.isNaN(value) ? 0 : value });
    }
}

export const stockMoveLineRowField = {
    component: StockMoveLineRowField,
    extractProps({ options }) {
        return {
            rowField: options.row_field,
            editable: Boolean(options.editable),
            dateFormat: options.date_format,
        };
    },
};

registry.category("fields").add("stock_move_line_row_field", stockMoveLineRowField);
