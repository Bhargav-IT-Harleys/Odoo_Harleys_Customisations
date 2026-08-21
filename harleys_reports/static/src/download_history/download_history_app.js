import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

// UI preview only - seed data stands in for real history rows until this view is approved.
// No ORM/RPC calls here on purpose.
const FORMAT_META = {
    csv: { label: "CSV", icon: "fa-file-text-o" },
    xlsx: { label: "XLSX", icon: "fa-file-excel-o" },
    pdf: { label: "PDF", icon: "fa-file-pdf-o" },
};

const SEED_HISTORY = [
    { id: 1, report: "Stock Report", format: "xlsx", filters: "As of 2026-08-19 · All Outlets", requested_at: "2026-08-19 18:42", size: "1.2 MB", rows: 4820, status: "ready" },
    { id: 2, report: "Physical Inventory Report", format: "csv", filters: "2026-08-18 · HYD-CS, BLR-CS", requested_at: "2026-08-18 21:05", size: "84 KB", rows: 212, status: "ready" },
    { id: 3, report: "Move History", format: "xlsx", filters: "2026-08-01 → 2026-08-17 · All Outlets", requested_at: "2026-08-17 10:30", size: "3.6 MB", rows: 17060, status: "ready" },
    { id: 4, report: "Cost Comparison", format: "pdf", filters: "Uploaded price list v3", requested_at: "2026-08-12 09:14", size: "410 KB", rows: 968, status: "ready" },
    { id: 5, report: "Internal Transfers", format: "csv", filters: "2026-07-01 → 2026-07-31 · MUM-CS", requested_at: "2026-08-02 16:50", size: "156 KB", rows: 1340, status: "expired" },
    { id: 6, report: "Stock Report", format: "xlsx", filters: "As of 2026-07-15 · VIJ-CS, NCR-CS", requested_at: "2026-07-16 08:20", size: "980 KB", rows: 3110, status: "expired" },
];

export class HarleysDownloadHistoryApp extends Component {
    static template = "harleys_reports.DownloadHistoryApp";
    static props = { ...standardActionServiceProps };

    setup() {
        this.user = user;
        this.notification = useService("notification");
        this.state = useState({ search: "" });
    }

    get entries() {
        const term = this.state.search.trim().toLowerCase();
        if (!term) {
            return SEED_HISTORY;
        }
        return SEED_HISTORY.filter(
            (entry) => entry.report.toLowerCase().includes(term) || entry.filters.toLowerCase().includes(term)
        );
    }

    formatMeta(format) {
        return FORMAT_META[format] || { label: format.toUpperCase(), icon: "fa-file-o" };
    }

    statusBadge(status) {
        return status === "ready" ? "text-bg-success" : "text-bg-secondary";
    }

    redownload(entry) {
        if (entry.status === "expired") {
            return;
        }
        this.notification.add(
            `"${entry.report}" (${this.formatMeta(entry.format).label}) will redownload here once this preview is wired up to real history.`,
            { title: "Download History — preview", type: "info" }
        );
    }
}

registry.category("actions").add("harleys_reports.download_history_app", HarleysDownloadHistoryApp);
