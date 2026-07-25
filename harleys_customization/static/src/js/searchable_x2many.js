import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import {
    StockMoveX2ManyField,
    MovesListRenderer,
    stockMoveX2ManyField,
} from "@stock/views/picking_form/stock_move_one2many";
import { useEffect, useState } from "@odoo/owl";

function stringifyValue(value) {
    if (value === null || value ===undefined) {
        return "";
    }
    if (typeof value === "string") {
        return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
        return String(value);
    }
    if (Array.isArray(value)) {
        return value.map(stringifyValue).join(" ");
    }
    if (typeof value === "object") {
        if (value.display_name) {
            return String(value.display_name);
        }
        if (value.name) {
            return String(value.name);
        }
        if (value.toString && value.toString !== Object.prototype.toString) {
            return String(value);
        }
        return "";
    }
    return String(value);
}

function getMany2OneId(value) {
    if (value === null || value === undefined) {
        return null;
    }
    if (Array.isArray(value)) {
        return value[0];
    }
    if (typeof value === "object") {
        return value.id || null;
    }
    return null;
}

function getMany2OneName(value) {
    if (value === null || value === undefined) {
        return "";
    }
    if (Array.isArray(value)) {
        return stringifyValue(value[1]);
    }
    if (typeof value === "object") {
        return stringifyValue(value.display_name || value.name || value);
    }
    return stringifyValue(value);
}

function getCategoryFieldName(records) {
    if (!records || !records.length) {
        return undefined;
    }

    const availableFields = Object.keys(records[0].data || {});
    const categoryCandidates = availableFields.filter((fieldName) =>
        /category|categ/i.test(fieldName)
    );

    return categoryCandidates.length ? categoryCandidates[0] : undefined;
}

export class FilterableListRenderer extends ListRenderer {
    static rowsTemplate = "harleys_customization.FilterableListRenderer.Rows";
    static props = [...ListRenderer.props, "searchValue?", "category?"];

    get categoryFieldName() {
        const records = this.props.list.records;
        if (!records || !records.length) {
            return undefined;
        }

        return getCategoryFieldName(records);
    }

    get filteredRecords() {
        const searchValue = (this.props.searchValue || "").trim().toLowerCase();
        const category = this.props.category;
        const list = this.props.list;

        if (!list || list.isGrouped || (!searchValue && !category)) {
            return list ? list.records : [];
        }

        const categoryFieldName = this.categoryFieldName;
        return list.records.filter((record) => {
            if (category && categoryFieldName) {
                const rawCategoryValue = record.data[categoryFieldName];
                const categoryId = getMany2OneId(rawCategoryValue);

                if (String(categoryId) !== category) {
                    return false;
                }
            }

            if (!searchValue) {
                return true;
            }

            const rowText = Object.values(record.data)
                .map(stringifyValue)
                .join(" ")
                .toLowerCase();

            return rowText.includes(searchValue);
        });
    }
}

export class SearchableMovesListRenderer extends MovesListRenderer {
    static rowsTemplate = "harleys_customization.SearchableStockMoveListRenderer.Rows";
    static props = [...MovesListRenderer.props, "searchValue?", "category?"];

    setup() {
        super.setup();
        // Batch/Batch Qty/Expiry Date need a real saved stock.move to work
        // (they read server-computed data a new, unsaved row doesn't have
        // yet), so save the picking as soon as a newly-added row gets a
        // product selected, instead of waiting for the user to save.
        this.autoSavedRecord = null;
        useEffect(
            () => {
                const record = this.editedRecord;
                if (
                    record &&
                    record.isNew &&
                    record.data.product_id &&
                    this.autoSavedRecord !== record
                ) {
                    this.autoSavedRecord = record;
                    this.env.model.root.save();
                }
            },
            () => [this.editedRecord, this.editedRecord && this.editedRecord.data.product_id]
        );
    }

    get categoryFieldName() {
        const records = this.props.list.records;
        if (!records || !records.length) {
            return undefined;
        }

        return getCategoryFieldName(records);
    }

    get filteredRecords() {
        const searchValue = (this.props.searchValue || "").trim().toLowerCase();
        const category = this.props.category;
        const list = this.props.list;

        if (!list || list.isGrouped || (!searchValue && !category)) {
            return list ? list.records : [];
        }

        const categoryFieldName = this.categoryFieldName;
        return list.records.filter((record) => {
            if (category && categoryFieldName) {
                const rawCategoryValue = record.data[categoryFieldName];
                const categoryId = getMany2OneId(rawCategoryValue);

                if (String(categoryId) !== category) {
                    return false;
                }
            }

            if (!searchValue) {
                return true;
            }

            const rowText = Object.values(record.data)
                .map(stringifyValue)
                .join(" ")
                .toLowerCase();

            return rowText.includes(searchValue);
        });
    }
}

function SearchableFieldMixin(Base) {
    return class SearchableField extends Base {
        static props = { ...Base.props };

        setup() {
            super.setup();
            this.filter = useState({ search: "", category: "" });
        }

        get listField() {
            return this.props.record && this.props.record.data
                ? this.props.record.data[this.props.name]
                : undefined;
        }

        get searchValue() {
            return (this.filter.search || "").trim().toLowerCase();
        }

        get categoryFieldName() {
            return getCategoryFieldName(this.listField?.records);
        }

        get categoryOptions() {
            if (!this.categoryFieldName) {
                return [];
            }

            const values = new Map();

            for (const record of this.listField.records) {
                const rawValue = record.data[this.categoryFieldName];
                const categoryId = getMany2OneId(rawValue);

                if (!categoryId) {
                    continue;
                }

                const categoryName = getMany2OneName(rawValue);

                if (!values.has(categoryId)) {
                    values.set(categoryId, {
                        id: categoryId,
                        name: categoryName,
                    });
                }
            }

            return Array.from(values.values()).sort((a, b) =>
                a.name.localeCompare(b.name)
            );
        }

        get hasActiveFilter() {
            return !!this.searchValue || !!this.filter.category;
        }

        get rendererProps() {
            const props = super.rendererProps;

            return {
                ...props,
                searchValue: this.searchValue,
                category: this.filter.category,
            };
        }

        get showPager() {
            const list = this.list;
            return !!list && !this.hasActiveFilter && list.count > list.limit;
        }

        onSearchInput(event) {
            this.filter.search = event.target.value;
        }

        onCategoryChange(event) {
            this.filter.category = event.target.value;
        }

        clearFilters() {
            this.filter.search = "";
            this.filter.category = "";
        }
    };
}

export class SearchableX2ManyField extends SearchableFieldMixin(X2ManyField) {
    static template = "harleys_customization.SearchableX2ManyField";
    static components = {
        ...X2ManyField.components,
        ListRenderer: FilterableListRenderer,
    };
}

export class SearchableStockMoveOne2ManyField extends SearchableFieldMixin(StockMoveX2ManyField) {
    static template = "harleys_customization.SearchableX2ManyField";
    static components = {
        ...StockMoveX2ManyField.components,
        ListRenderer: SearchableMovesListRenderer,
    };
}

export const searchableX2ManyField = {
    ...x2ManyField,
    component: SearchableX2ManyField,
};

registry.category("fields").add(
    "searchable_x2many",
    searchableX2ManyField
);

export const searchableStockMoveX2ManyField = {
    ...stockMoveX2ManyField,
    component: SearchableStockMoveOne2ManyField,
};

registry.category("fields").add(
    "searchable_stock_move_one2many",
    searchableStockMoveX2ManyField
);