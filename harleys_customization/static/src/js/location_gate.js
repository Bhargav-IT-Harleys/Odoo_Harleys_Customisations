import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SearchPanel } from "@web/search/search_panel/search_panel";
import { SearchModel } from "@web/search/search_model";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { InventoryReportListView } from "@stock/views/list/inventory_report_list_view";
import { StockReportListView } from "@stock/views/list/stock_report_list_view";
import { StockReportSearchPanel } from "@stock/views/search/stock_report_search_panel";

export const LOCATION_GATE_FIELD = "location_id";
export const LOCATION_GATE_ALL_CLICKED_EVENT = "harleys_location_gate_all_clicked";
const LOCATION_GATE_TEMPLATE = "harleys_customization.LocationGatedListView";

export function getLocationCategory(searchModel) {
    const [category] = searchModel.getSections(
        (section) => section.type === "category" && section.fieldName === LOCATION_GATE_FIELD
    );
    return category;
}

export function getSelectedLocationValue(searchModel) {
    const category = getLocationCategory(searchModel);
    if (!category || !category.activeValueId) {
        return null;
    }
    return category.values.get(category.activeValueId) || null;
}

export const LocationGateListController = (Base) =>
    class extends Base {
        setup() {
            super.setup();
            this.locationGateDialog = useService("dialog");
            this.locationGateState = useState({ hasInteracted: false });
            const markInteracted = () => {
                this.locationGateState.hasInteracted = true;
            };
            useBus(this.env.searchModel, "update", markInteracted);
            useBus(this.env.searchModel, LOCATION_GATE_ALL_CLICKED_EVENT, markInteracted);
        }

        get selectedLocation() {
            return getSelectedLocationValue(this.env.searchModel);
        }

        get locationGateMode() {
            if (this.selectedLocation) {
                return "specific";
            }
            return this.locationGateState.hasInteracted ? "all" : "none";
        }

        async createRecord(...args) {
            const location = this.selectedLocation;
            if (!location) {
                this.locationGateDialog.add(ConfirmationDialog, {
                    title: _t("Select a Location"),
                    body: _t("Pick a location from the panel on the left before creating a new line."),
                    confirmLabel: _t("Ok"),
                });
                return;
            }
            const result = await super.createRecord(...args);
            const record = this.model.root.editedRecord;
            if (record && LOCATION_GATE_FIELD in record.data) {
                await record.update({
                    [LOCATION_GATE_FIELD]: { id: location.id, display_name: location.display_name },
                });
            }
            return result;
        }
    };

export class LocationGateSearchPanel extends SearchPanel {
    static template = "harleys_customization.LocationSearchPanel";

    setup() {
        super.setup();
        this.locationSearchState = useState({ text: "" });
    }

    get locationSearchText() {
        return this.locationSearchState.text;
    }

    onLocationSearchInput(ev) {
        this.locationSearchState.text = ev.target.value;
    }

    filteredLocationValues(section) {
        const query = this.locationSearchState.text.trim().toLowerCase();
        return [...section.values.values()].filter(
            (value) => value.id !== false && value.display_name.toLowerCase().includes(query)
        );
    }

    async toggleCategory(category, value) {
        if (
            category.type === "category" &&
            category.fieldName === LOCATION_GATE_FIELD &&
            category.activeValueId === value.id
        ) {
            this.env.searchModel.trigger(LOCATION_GATE_ALL_CLICKED_EVENT);
        }
        this.locationSearchState.text = "";
        return super.toggleCategory(category, value);
    }
}

const withCreateConfirmation = (title, body) => (Base) =>
    class extends Base {
        setup() {
            super.setup();
            this.createConfirmDialog = useService("dialog");
        }

        createRecord(...args) {
            if (!this.selectedLocation) {
                return super.createRecord(...args);
            }
            return new Promise((resolve) => {
                this.createConfirmDialog.add(ConfirmationDialog, {
                    title,
                    body,
                    confirm: () => resolve(super.createRecord(...args)),
                    cancel: () => resolve(),
                });
            });
        }
    };

class StockScrapListRenderer extends ListRenderer {
    isInlineEditable(record) {
        return super.isInlineEditable(record) && record.data.state !== "done";
    }
}

class StockScrapListController extends withCreateConfirmation(
    _t("New Inv Adjustment"),
    _t(
        "This creates a new inventory adjustment line. Make sure the location " +
            "and product are correct before applying. Continue?"
    )
)(LocationGateListController(ListController)) {
    static template = LOCATION_GATE_TEMPLATE;
}

registry.category("views").add("stock_scrap_list", {
    ...listView,
    Renderer: StockScrapListRenderer,
    Controller: StockScrapListController,
    SearchPanel: LocationGateSearchPanel,
});

class PhysicalInventoryListController extends withCreateConfirmation(
    _t("New Physical Inventory Count"),
    _t(
        "This starts a new inventory count line. Make sure the location " +
            "and product are correct before applying. Continue?"
    )
)(LocationGateListController(ListController)) {
    static template = LOCATION_GATE_TEMPLATE;
}

class SharedLocationGatedListController extends LocationGateListController(ListController) {
    static template = LOCATION_GATE_TEMPLATE;
}

// Moves History and Internal Transfers only get a plain sidebar filter, not the location gate's
// blocking/placeholder UI or any server-side access restriction - a move or transfer always
// touches a location on either end, so narrowing to "my" locations would hide valid records
// (e.g. every incoming receipt, whose source is a vendor location, not an internal one).
// Moves History still gets its own SearchModel below: a move either leaves from or arrives at a
// location, so picking one in the sidebar should match either side, not just the source.
class MovesHistorySearchModel extends SearchModel {
    _getCategoryDomain(excludedCategoryId) {
        const domain = [];
        for (const category of this.categories) {
            if (category.id === excludedCategoryId || !category.activeValueId) {
                continue;
            }
            if (category.fieldName === LOCATION_GATE_FIELD) {
                domain.push(
                    "|",
                    [LOCATION_GATE_FIELD, "child_of", category.activeValueId],
                    ["location_dest_id", "child_of", category.activeValueId]
                );
                continue;
            }
            const field = this.searchViewFields[category.fieldName];
            const operator = field.type === "many2one" && category.parentField ? "child_of" : "=";
            domain.push([category.fieldName, operator, category.activeValueId]);
        }
        return domain;
    }
}

registry.category("views").add("stock_move_line_history_list", {
    ...listView,
    SearchModel: MovesHistorySearchModel,
    SearchPanel: LocationGateSearchPanel,
});

registry.category("views").add("stock_picking_internal_list", {
    ...listView,
    SearchPanel: LocationGateSearchPanel,
});

const INVENTORY_REPORT_CONTROLLERS = {
    physical_inventory_list: PhysicalInventoryListController,
    stock_quant_locations_list: SharedLocationGatedListController,
};

for (const [jsClass, Controller] of Object.entries(INVENTORY_REPORT_CONTROLLERS)) {
    registry.category("views").add(jsClass, {
        ...InventoryReportListView,
        Controller,
        SearchPanel: LocationGateSearchPanel,
    });
}

// Stock report has no "my location" domain restriction at all (core's own warehouse-context
// mechanism never filters records, only recomputes quantity columns - see SESSIONS.md) - this is
// blocking-placeholder UI only, same as the other screens' "pick a location first" nudge.
class WarehouseGatedListController extends ListController {
    static template = LOCATION_GATE_TEMPLATE;

    setup() {
        super.setup();
        this.locationGateState = useState({ hasInteracted: false });
        useBus(this.env.searchModel, "update", () => {
            this.locationGateState.hasInteracted = true;
        });
    }

    get selectedLocation() {
        const warehouseId = this.env.searchModel.globalContext?.warehouse_id;
        if (!warehouseId) {
            return null;
        }
        const warehouse = (this.env.searchModel.getWarehouses?.() || []).find(
            (w) => w.id === warehouseId
        );
        return warehouse ? { id: warehouse.id, display_name: warehouse.name } : null;
    }

    get locationGateMode() {
        if (this.selectedLocation) {
            return "specific";
        }
        return this.locationGateState.hasInteracted ? "all" : "none";
    }
}

class WarehouseSearchPanel extends StockReportSearchPanel {
    setup() {
        super.setup();
        this.warehouseSearchState = useState({ text: "" });
    }

    get warehouseSearchText() {
        return this.warehouseSearchState.text;
    }

    onWarehouseSearchInput(ev) {
        this.warehouseSearchState.text = ev.target.value;
    }

    get filteredWarehouses() {
        const query = this.warehouseSearchState.text.trim().toLowerCase();
        if (!query) {
            return this.warehouses;
        }
        return this.warehouses.filter((warehouse) => warehouse.name.toLowerCase().includes(query));
    }

    applyWarehouseContext(warehouseId) {
        super.applyWarehouseContext(warehouseId);
        this.warehouseSearchState.text = "";
    }
}

registry.category("views").add("stock_report_list_view_gated", {
    ...StockReportListView,
    Controller: WarehouseGatedListController,
    SearchPanel: WarehouseSearchPanel,
});

