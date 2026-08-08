import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useBus, useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SearchPanel } from "@web/search/search_panel/search_panel";

export const LOCATION_GATE_FIELD = "location_id";
export const LOCATION_GATE_ALL_CLICKED_EVENT = "harleys_location_gate_all_clicked";

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
                    body: _t(
                        "Pick a location from the panel on the left before creating a new line."
                    ),
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
    async toggleCategory(category, value) {
        if (
            category.type === "category" &&
            category.fieldName === LOCATION_GATE_FIELD &&
            category.activeValueId === value.id
        ) {
            this.env.searchModel.trigger(LOCATION_GATE_ALL_CLICKED_EVENT);
        }
        return super.toggleCategory(category, value);
    }
}
