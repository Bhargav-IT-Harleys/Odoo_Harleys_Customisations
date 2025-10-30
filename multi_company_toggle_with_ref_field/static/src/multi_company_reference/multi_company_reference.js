/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { SwitchCompanyItem } from "@web/webclient/switch_company_menu/switch_company_item";
import { SwitchCompanyMenu } from "@web/webclient/switch_company_menu/switch_company_menu";
import { rpc } from "@web/core/network/rpc";
import { user, userBus } from "@web/core/user";


patch(SwitchCompanyItem.prototype, {
    setup() {
        onWillStart(async () => { 
            const compId = this.props.company.id
            const company_ref = await rpc("/action_company_reference", {
                company_id : compId,
              });
            this.props.company_reference = company_ref
            });
         super.setup();
   }
});

patch(SwitchCompanyMenu.prototype, {
    setup() {
        onWillStart(async () => { 
              this.props.selected_company_reference = await rpc("/action_company_reference", {
                company_id : user.activeCompany.id,
              });
            });
         super.setup();
   }
});