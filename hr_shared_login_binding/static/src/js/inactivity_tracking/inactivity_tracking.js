import { registry } from "@web/core/registry";

console.log("[hr_inactivity] module loading...");

const inactivityService = {
    dependencies: ["presence"],
    start(env, { presence }) {
        console.log("[hr_inactivity] service starting, presence available:", !!presence);
        try {
            if (!presence || typeof presence.getInactivityPeriod !== "function" || !presence.bus) {
                console.warn("[hr_inactivity] presence service not ready, skipping");
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
                    console.log("[hr_inactivity] check:", remaining, "ms remaining");
                    if (remaining <= 0) {
                        console.log("[hr_inactivity] timeout reached, logging out");
                        logout();
                        return;
                    }
                    timer = setTimeout(check, Math.min(remaining, 1000));
                } catch (e) {
                    console.error("[hr_inactivity] check error:", e);
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
        } catch (e) {
            console.error("[hr_inactivity] service start error:", e);
            return {};
        }
    },
};

try {
    registry.category("services").add("hr_inactivity", inactivityService);
    console.log("[hr_inactivity] service registered successfully");
} catch (e) {
    console.error("[hr_inactivity] service registration failed:", e);
}
