import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ListController } from "@web/views/list/list_controller";
import { LocationGateListController, LocationGateSearchPanel } from "./location_gate";

class PhysicalInventoryListController extends LocationGateListController(ListController) {
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
        title: _t("New Physical Inventory Count"),
        body: _t(
          "This starts a new inventory count line. Make sure the location " +
            "and product are correct before applying. Continue?"
        ),
        confirm: () => resolve(super.createRecord(...args)),
        cancel: () => resolve(),
      });
    });
  }
}

registry.category("views").add(
  "inventory_report_list",
  {
    ...registry.category("views").get("inventory_report_list"),
    Controller: PhysicalInventoryListController,
    SearchPanel: LocationGateSearchPanel,
  },
  { force: true }
);
