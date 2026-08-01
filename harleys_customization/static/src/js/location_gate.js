import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// Must match the field name used on the <searchpanel> category in
// stock_scrap_views.xml / stock_quant_views.xml.
export const LOCATION_GATE_FIELD = "location_id";

export function getLocationCategory(searchModel) {
    const [category] = searchModel.getSections(
        (section) => section.type === "category" && section.fieldName === LOCATION_GATE_FIELD
    );
    return category;
}

// search panel categories default their activeValueId to false (the built-in
// "All" value - confirmed against search_model.js's _createCategoryTree,
// category.rootIds always starts with [false]) - so "nothing picked yet" and
// "All explicitly picked" are the same state here, which is what we want:
// there is no "All" option surfaced to these users at all.
export function getSelectedLocationValue(searchModel) {
    const category = getLocationCategory(searchModel);
    if (!category || !category.activeValueId) {
        return null;
    }
    return category.values.get(category.activeValueId) || null;
}

// Mixin applied to a ListController subclass: hides/blocks the list (via the
// harleys_customization.LocationGatedListView template) and the create flow
// until a location category value is selected, then stamps that location
// onto every new inline row instead of whatever default the field would
// otherwise pick.
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
