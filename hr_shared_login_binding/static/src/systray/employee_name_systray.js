import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { user } from "@web/core/user";

export class EmployeeNameSystray extends Component {
    static template = "hr_shared_login_binding.EmployeeNameSystray";
    static props = {};

    get employeeName() {
        return session.harleys_acting_employee_name;
    }

    get label() {
        if (this.employeeName && this.employeeName !== user.name) {
            return `${user.name} · ${this.employeeName}`;
        }
        return this.employeeName || user.name;
    }

    get tooltip() {
        const lines = [`${_t("User")}: ${user.name}`];
        if (this.employeeName && this.employeeName !== user.name) {
            lines.push(`${_t("Employee")}: ${this.employeeName}`);
        }
        return lines.join("\n");
    }
}

registry.category("systray").add(
    "hr_shared_login_binding.EmployeeNameSystray",
    { Component: EmployeeNameSystray },
    { sequence: 10 }
);
