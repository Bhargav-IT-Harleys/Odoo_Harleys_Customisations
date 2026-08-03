import { Component, useState, useChildSubEnv } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
import { user, userBus } from "@web/core/user";
import { CompanySelector } from "@web/webclient/switch_company_menu/switch_company_menu";
import { SwitchCompanyItem } from "@web/webclient/switch_company_menu/switch_company_item";

function getCompany(id) {
    return user.allowedCompaniesWithAncestors.find((c) => c.id === id);
}

export class CompanySelectionOverlay extends Component {
    static template = "hr_shared_login_binding.CompanySelectionOverlay";
    static components = { SwitchCompanyItem };
    static props = {};

    setup() {
        this.state = useState({ visible: this._shouldShow() });
        const actionService = useService("action");
        this.companySelector = useState(new CompanySelector(actionService, {}));
        this.companySelector.selectedCompaniesIds.splice(0);
        useChildSubEnv({ companySelector: this.companySelector });
        useBus(userBus, "ACTIVE_COMPANIES_CHANGED", () => this.dismiss());
    }

    _shouldShow() {
        return !!session.harleys_force_company_selection;
    }

    get companies() {
        const result = [];
        const addCompany = (company, level = 0) => {
            result.push({ company, level });
            for (const childId of company.child_ids || []) {
                addCompany(getCompany(childId), level + 1);
            }
        };
        user.allowedCompaniesWithAncestors
            .filter((c) => !c.parent_id)
            .sort((c1, c2) => c1.sequence - c2.sequence)
            .forEach((c) => addCompany(c));
        return result;
    }

    get canConfirm() {
        return this.companySelector.selectedCompaniesIds.length > 0;
    }

    get message() {
        return _t("Select the companies you want to work with, then click Confirm to proceed.");
    }

    async confirm() {
        if (!this.canConfirm) {
            return;
        }
        // apply() ends in a real browser reload (router.pushState with
        // reload:true) - the ack must be awaited and complete first, or the
        // reload races it and the server never sees it, showing this again.
        await rpc("/harleys_company_login_popup/dismiss", {}).catch(() => {});
        this.state.visible = false;
        this.companySelector.apply();
    }

    dismiss() {
        if (this.state.visible) {
            rpc("/harleys_company_login_popup/dismiss", {}).catch(() => {});
        }
        this.state.visible = false;
    }
}

registry.category("main_components").add("hr_shared_login_binding.CompanySelectionOverlay", {
    Component: CompanySelectionOverlay,
});
