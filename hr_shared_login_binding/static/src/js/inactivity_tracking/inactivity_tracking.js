import { registry } from "@web/core/registry";
import { session } from "@web/session";

import { presenceService } from "@bus/services/presence_service";

const INACTIVITY_LOGIN_URL = "/web/login";

const inactivityService = {
    dependencies: ["presence"],
    start(env, { presence }) {
        let timer = null;

        const logout = () => {
            window.location.replace("/web/session/logout?redirect=/web/login");
        };

        const startTimer = () => {
            clearTimeout(timer);
            if (!session.lock_timeout_inactivity) return;
            const remaining = session.lock_timeout_inactivity * 1000 - presence.getInactivityPeriod();
            if (remaining <= 0) {
                logout();
                return;
            }
            timer = setTimeout(startTimer, Math.min(remaining, 1000));
        };

        presence.bus.addEventListener("presence", startTimer);
        startTimer();

        return {
            stop() {
                clearTimeout(timer);
            },
        };
    },
};

registry.category("services").add("hr_inactivity", inactivityService, { force: true });
