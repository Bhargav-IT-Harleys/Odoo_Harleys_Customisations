import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { LocationGateListController, LocationGateSearchPanel } from "./location_gate";

export class StockScrapListRenderer extends ListRenderer {
    isInlineEditable(record) {
        return super.isInlineEditable(record) && record.data.state !== "done";
    }
}

export class StockScrapListController extends LocationGateListController(ListController) {
    static template = "harleys_customization.LocationGatedListView";
}

export const stockScrapListView = {
    ...listView,
    Renderer: StockScrapListRenderer,
    Controller: StockScrapListController,
    SearchPanel: LocationGateSearchPanel,
};

registry.category("views").add("stock_scrap_list", stockScrapListView);
