import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { LocationGateListController, LocationGateSearchPanel } from "./location_gate";

export class StockScrapListRenderer extends ListRenderer {
    isInlineEditable(record) {
        return super.isInlineEditable(record) && record.data.state !== "done";
    }
}

export class StockScrapListController extends LocationGateListController(ListController) {
    static template = "harleys_customization.LocationGatedListView";

        setup() {
        super.setup();
        this.dialog = useService("dialog");
    }

    createRecord(...args) {
        if (!this.selectedLocation) {
            return super.createRecord(...args);
        }
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("New Inv Adjustment"),
                body: _t(
                    "This creates a new inventory adjustment line. Make sure the location " +
                        "and product are correct before applying. Continue?"
                ),
                confirm: () => resolve(super.createRecord(...args)),
                cancel: () => resolve(),
            });
        });
    }
}

export const stockScrapListView = {
    ...listView,
    Renderer: StockScrapListRenderer,
    Controller: StockScrapListController,
    SearchPanel: LocationGateSearchPanel,
};

registry.category("views").add("stock_scrap_list", stockScrapListView);
