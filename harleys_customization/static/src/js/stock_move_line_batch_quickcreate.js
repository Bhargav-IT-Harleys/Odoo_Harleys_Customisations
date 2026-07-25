import { Component, useRef, useState } from "@odoo/owl";
import { useAutofocus, useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { today } from "@web/core/l10n/dates";

/**
 * Content of the Receipt "Add Batch" popover: a batch number input with
 * live search against existing stock.lot records, and - only when nothing
 * matches and the product tracks expiry - a required expiry date input
 * (fixed dd/MM/yy format, no backdating).
 */
export class StockMoveLineBatchQuickCreate extends Component {
    static template = "harleys_customization.StockMoveLineBatchQuickCreate";
    static components = { DateTimeInput };
    static props = {
        close: Function,
        showExpiryField: Boolean,
        productId: { type: [Number, Boolean], optional: true },
        onCreate: Function,
        onSelectExisting: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            matches: [],
            error: "",
            expiryValue: null,
        });
        this.nameRef = useRef("name");
        useAutofocus({ refName: "name" });
        this.debouncedSearch = useDebounced(this.search, 300);
    }

    get showExpiry() {
        return this.props.showExpiryField && this.state.matches.length === 0;
    }

    onNameInput() {
        this.state.error = "";
        this.debouncedSearch();
    }

    onNameKeydown(ev) {
        if (ev.key === "Enter") {
            this.confirmCreate();
        }
    }

    onExpiryChange(value) {
        this.state.expiryValue = value;
        this.state.error = "";
    }

    async search() {
        const query = this.nameRef.el?.value?.trim();
        if (!query) {
            this.state.matches = [];
            return;
        }
        const domain = [["name", "ilike", query]];
        if (this.props.productId) {
            domain.push(["product_id", "=", this.props.productId]);
        }
        this.state.matches = await this.orm.searchRead("stock.lot", domain, ["id", "name"], {
            limit: 6,
        });
    }

    selectExisting(lot) {
        this.props.onSelectExisting(lot.id);
    }

    confirmCreate() {
        const name = this.nameRef.el?.value?.trim();
        if (!name) {
            this.state.error = "Enter a batch number.";
            return;
        }
        let expiry = false;
        if (this.showExpiry) {
            if (!this.state.expiryValue) {
                this.state.error = "Expiry date is required for this product.";
                return;
            }
            if (this.state.expiryValue < today()) {
                this.state.error = "Expiry date cannot be in the past.";
                return;
            }
            expiry = this.state.expiryValue.toISODate();
        }
        this.props.onCreate(name, expiry);
    }
}
