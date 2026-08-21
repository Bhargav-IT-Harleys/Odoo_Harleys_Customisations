import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { buildClientCsv, downloadClientCsv } from "../common/csv_utils";

const GRID_PAGE_SIZE = 20;
const GRID_COLUMNS = [
    { key: "product_name", label: "Product" },
    { key: "sku", label: "SKU" },
    { key: "warehouse_name", label: "Warehouse" },
    { key: "system_cost", label: "System Cost" },
    { key: "uploaded_price", label: "Uploaded Price" },
    { key: "variance_abs", label: "Variance" },
    { key: "variance_pct", label: "Variance %" },
    { key: "status", label: "Status" },
];
const STATUS_META = {
    increased: { label: "Increased", icon: "fa-arrow-up", cls: "cc-badge-increased" },
    decreased: { label: "Decreased", icon: "fa-arrow-down", cls: "cc-badge-decreased" },
    unchanged: { label: "Unchanged", icon: "fa-minus", cls: "cc-badge-unchanged" },
    no_baseline: { label: "No Prior Cost", icon: "fa-question", cls: "cc-badge-no-baseline" },
};

export class HarleysCostComparisonApp extends Component {
    static template = "harleys_reports.CostComparisonApp";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            computing: false,
            downloadingTemplate: false,
            error: "",
            warehouses: [],
            screen: "setup",
            setup: {
                file: null,
                fileContent: "",
                selectedWarehouses: [],
                warehouseSearch: "",
            },
            activeComparison: null,
            history: [],
            grid: {
                search: "",
                status: "",
                warehouseCode: "",
                sort: { key: "variance_pct", direction: "desc" },
                offset: 0,
            },
        });
        for (const name of [
            "onFileChange", "downloadTemplate", "toggleWarehouse", "toggleAllWarehouses", "toggleRegion",
            "setWarehouseSearch", "runComparison", "openHistoryComparison", "newComparison", "goHistory",
            "setGridSearch", "setGridStatus", "setGridWarehouse", "sortGridBy", "previousGridPage",
            "nextGridPage", "exportGridCsv",
        ]) {
            this[name] = this[name].bind(this);
        }
        onWillStart(() => this.loadWarehouses());
    }

    async loadWarehouses() {
        try {
            this.state.warehouses = await this.orm.call("harleys.reports.service", "get_cost_comparison_warehouses");
            this.state.setup.selectedWarehouses = this.state.warehouses.map((w) => w.code);
        } catch (error) {
            this.showError(error, "Warehouses could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    async onFileChange(event) {
        const file = event.target.files[0];
        if (!file) {
            this.state.setup.file = null;
            this.state.setup.fileContent = "";
            return;
        }
        this.state.setup.file = { name: file.name, size: file.size };
        this.state.setup.fileContent = await file.text();
    }

    async downloadTemplate() {
        if (this.state.downloadingTemplate) {
            return;
        }
        this.state.downloadingTemplate = true;
        try {
            const products = await this.orm.call("harleys.reports.service", "get_cost_comparison_template_products");
            const columns = [
                { key: "sku", label: "Internal Reference" },
                { key: "name", label: "Product Name" },
                { key: "category", label: "Product Category" },
                { key: "price", label: "Price" },
            ];
            const rows = products.map((product) => ({ ...product, price: "" }));
            downloadClientCsv("cost_comparison_template.csv", buildClientCsv(columns, rows));
        } catch (error) {
            this.showError(error, "The template could not be generated.");
        } finally {
            this.state.downloadingTemplate = false;
        }
    }

    toggleWarehouse(code) {
        const selected = this.state.setup.selectedWarehouses;
        this.state.setup.selectedWarehouses = selected.includes(code)
            ? selected.filter((item) => item !== code)
            : [...selected, code];
    }

    setWarehouseSearch(event) {
        this.state.setup.warehouseSearch = event.target.value;
    }

    get filteredWarehouses() {
        const term = this.state.setup.warehouseSearch.trim().toLowerCase();
        if (!term) {
            return this.state.warehouses;
        }
        return this.state.warehouses.filter((wh) =>
            wh.name.toLowerCase().includes(term) ||
            wh.warehouse_code.toLowerCase().includes(term) ||
            wh.region.toLowerCase().includes(term)
        );
    }

    get groupedWarehouses() {
        const groups = new Map();
        for (const wh of this.filteredWarehouses) {
            if (!groups.has(wh.region)) {
                groups.set(wh.region, []);
            }
            groups.get(wh.region).push(wh);
        }
        return Array.from(groups.entries())
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([region, warehouses]) => ({ region, warehouses }));
    }

    toggleAllWarehouses() {
        const visibleCodes = this.filteredWarehouses.map((wh) => wh.code);
        const allVisibleSelected = visibleCodes.every((code) => this.state.setup.selectedWarehouses.includes(code));
        this.state.setup.selectedWarehouses = allVisibleSelected
            ? this.state.setup.selectedWarehouses.filter((code) => !visibleCodes.includes(code))
            : Array.from(new Set([...this.state.setup.selectedWarehouses, ...visibleCodes]));
    }

    toggleRegion(region) {
        const regionCodes = this.state.warehouses.filter((wh) => wh.region === region).map((wh) => wh.code);
        const allSelected = regionCodes.every((code) => this.state.setup.selectedWarehouses.includes(code));
        this.state.setup.selectedWarehouses = allSelected
            ? this.state.setup.selectedWarehouses.filter((code) => !regionCodes.includes(code))
            : Array.from(new Set([...this.state.setup.selectedWarehouses, ...regionCodes]));
    }

    get canRun() {
        return !!this.state.setup.fileContent && this.state.setup.selectedWarehouses.length > 0;
    }

    async runComparison() {
        if (!this.canRun || this.state.computing) {
            return;
        }
        this.state.computing = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("harleys.reports.service", "compute_cost_comparison", [
                this.state.setup.fileContent,
                this.state.setup.selectedWarehouses,
            ]);
            const entry = {
                id: `cmp-${this.state.history.length + 1}`,
                name: this.state.setup.file?.name || "Cost Comparison",
                ...result,
            };
            this.state.history.unshift(entry);
            this.showComparison(entry);
        } catch (error) {
            this.showError(error, "The comparison could not be computed.");
        } finally {
            this.state.computing = false;
        }
    }

    openHistoryComparison(id) {
        const entry = this.state.history.find((item) => item.id === id);
        if (entry) {
            this.showComparison(entry);
        }
    }

    showComparison(entry) {
        this.state.activeComparison = entry;
        this.state.grid = { search: "", status: "", warehouseCode: "", sort: { key: "variance_pct", direction: "desc" }, offset: 0 };
        this.state.screen = "results";
    }

    warehouseBarSegments(warehouse) {
        const total = warehouse.total || 1;
        return [
            { cls: "cc-seg-increased", pct: (warehouse.increased / total) * 100 },
            { cls: "cc-seg-decreased", pct: (warehouse.decreased / total) * 100 },
            { cls: "cc-seg-unchanged", pct: (warehouse.unchanged / total) * 100 },
            { cls: "cc-seg-no-baseline", pct: (warehouse.no_baseline / total) * 100 },
        ];
    }

    statusMeta(status) {
        return STATUS_META[status];
    }

    newComparison() {
        this.state.setup.file = null;
        this.state.setup.fileContent = "";
        this.state.screen = "setup";
    }

    goHistory() {
        this.state.screen = "history";
    }

    setGridSearch(event) {
        this.state.grid.search = event.target.value;
        this.state.grid.offset = 0;
    }

    setGridStatus(event) {
        this.state.grid.status = event.target.value;
        this.state.grid.offset = 0;
    }

    setGridWarehouse(event) {
        this.state.grid.warehouseCode = event.target.value;
        this.state.grid.offset = 0;
    }

    sortGridBy(key) {
        const { sort } = this.state.grid;
        const direction = sort.key === key && sort.direction === "asc" ? "desc" : "asc";
        this.state.grid.sort = { key, direction };
        this.state.grid.offset = 0;
    }

    get filteredSortedLines() {
        const { search, status, warehouseCode, sort } = this.state.grid;
        const term = search.trim().toLowerCase();
        let lines = this.state.activeComparison.lines.filter((line) => {
            if (status && line.status !== status) return false;
            if (warehouseCode && line.warehouse_code !== warehouseCode) return false;
            if (term && !line.product_name.toLowerCase().includes(term) && !line.sku.toLowerCase().includes(term)) return false;
            return true;
        });
        lines = [...lines].sort((a, b) => {
            const left = a[sort.key] ?? 0;
            const right = b[sort.key] ?? 0;
            const comparison = typeof left === "number" && typeof right === "number"
                ? left - right
                : String(left).localeCompare(String(right));
            return sort.direction === "asc" ? comparison : -comparison;
        });
        return lines;
    }

    get gridPageRows() {
        return this.filteredSortedLines.slice(this.state.grid.offset, this.state.grid.offset + GRID_PAGE_SIZE);
    }

    get gridTotal() {
        return this.filteredSortedLines.length;
    }

    get gridPageSize() {
        return GRID_PAGE_SIZE;
    }

    get gridPageNumber() {
        return Math.floor(this.state.grid.offset / GRID_PAGE_SIZE) + 1;
    }

    get gridPageCount() {
        return Math.max(1, Math.ceil(this.gridTotal / GRID_PAGE_SIZE));
    }

    previousGridPage() {
        this.state.grid.offset = Math.max(0, this.state.grid.offset - GRID_PAGE_SIZE);
    }

    nextGridPage() {
        if (this.state.grid.offset + GRID_PAGE_SIZE < this.gridTotal) {
            this.state.grid.offset += GRID_PAGE_SIZE;
        }
    }

    exportGridCsv() {
        const csv = buildClientCsv(GRID_COLUMNS, this.filteredSortedLines);
        downloadClientCsv(`${this.state.activeComparison.id}.csv`, csv);
    }

    showError(error, fallback) {
        const message = error?.data?.message || error?.message || fallback;
        this.state.error = message;
        this.notification.add(message, { title: "Cost Comparison", type: "danger" });
    }
}

registry.category("actions").add("harleys_reports.cost_comparison_app", HarleysCostComparisonApp);
