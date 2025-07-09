/** @odoo-module **/

import {browser} from "@web/core/browser/browser";
import {registry} from "@web/core/registry";

export const deviceService = {
    dependencies: ["rpc"],
    start(_, {rpc}) {
        let requestSent = false;

        const updateDevice = async () => {
            if (!requestSent) {
                try {
                    requestSent = true;
                    await rpc("/web/session/update_device", {});
                    console.log("Device information updated successfully");
                } catch (error) {
                    console.error("Failed to update device information:", error);
                    requestSent = false;
                }
            }
        };

        browser.setTimeout(() => {
            updateDevice();
        }, 2000);

        const userActivityEvents = ["visibilitychange"];

        const activityListeners = {};
        userActivityEvents.forEach((eventType) => {
            const listener = () => {
                if (
                    eventType === "visibilitychange" &&
                    document.visibilityState === "visible" &&
                    !requestSent
                ) {
                    updateDevice();
                }
            };
            activityListeners[eventType] = listener;
            browser.addEventListener(window, eventType, listener);
        });

        return () => {
            userActivityEvents.forEach((eventType) => {
                browser.removeEventListener(
                    window,
                    eventType,
                    activityListeners[eventType]
                );
            });
        };
    },
};

registry.category("services").add("device", deviceService);
