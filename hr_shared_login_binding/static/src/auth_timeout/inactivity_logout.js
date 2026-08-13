import { CheckIdentityDialog } from "@auth_timeout/services/check_identity/check_identity";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";

const message = encodeURIComponent("Session automatically logged out due to inactivity.");
const loginUrl = `/web/login?message=${message}`;
const logoutUrl = `/web/session/logout?redirect=${encodeURIComponent(loginUrl)}`;

patch(CheckIdentityDialog.prototype, {
    setup() {
        super.setup(...arguments);
        browser.location.replace(logoutUrl);
    },
});
