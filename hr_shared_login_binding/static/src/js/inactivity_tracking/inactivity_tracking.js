import { registry } from "@web/core/registry";

const inactivityService = {
    dependencies: ["presence"],
    start(env, { presence }) {
        try {
            if (!presence || typeof presence.getInactivityPeriod !== "function" || !presence.bus) {
                return {};
            }

            let timer = null;
            let channel = null;

            const logout = () => {
                try {
                    if (channel) {
                        channel.close();
                        channel = null;
                    }
                } catch {
                    // ignore
                }
                window.location.replace("/web/session/logout?redirect=/web/login");
            };

            const check = () => {
                try {
                    clearTimeout(timer);
                    const s = window.session || {};
                    if (typeof s.hr_inactivity_timeout === "undefined") return;
                    if (s.hr_inactivity_timeout <= 0) return;
                    const remaining = s.hr_inactivity_timeout * 1000 - presence.getInactivityPeriod();
                    if (remaining <= 0) {
                        logout();
                        return;
                    }
                    timer = setTimeout(check, Math.min(remaining, 1000));
                } catch {
                    // ignore
                }
            };

            try {
                channel = new BroadcastChannel("hr_inactivity_channel");
                channel.addEventListener("message", (event) => {
                    if (event.data === "activity") {
                        check();
                    }
                });
            } catch {
                channel = null;
            }

            presence.bus.addEventListener("presence", () => {
                if (channel) {
                    try { channel.postMessage("activity"); } catch {}
                }
                check();
            });

            check();

            return {
                stop() {
                    clearTimeout(timer);
                    if (channel) {
                        channel.close();
                        channel = null;
                    }
                },
            };
        } catch {
            return {};
        }
    },
};

try {
    registry.category("services").add("hr_inactivity", inactivityService);
} catch {
    // ignore
}
