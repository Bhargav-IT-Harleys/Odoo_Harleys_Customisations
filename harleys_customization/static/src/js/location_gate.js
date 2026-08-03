import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

export const LOCATION_GATE_FIELD = "location_id";

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
        }

        get selectedLocation() {
            return getSelectedLocationValue(this.env.searchModel);
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
