import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Pager } from "@web/core/pager/pager";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { CheckBox } from "@web/core/checkbox/checkbox";

const MODEL_KEY_PREFIX = "model:";
const DYNAMIC_PAGE_SIZES = [40, 80, 200];
const DYNAMIC_DEFAULT_PAGE_SIZE = 80;
const DYNAMIC_MAXIMUM_PAGE_SIZE = 50000;
const DYNAMIC_DEFAULT_COLUMN_COUNT = 6;
const MAX_FAVORITES = 3;
const DEFAULT_REPORT_KEY = "stock_report";

export class HarleysReportsApp extends Component {
    static template = "harleys_reports.ReportsApp";
    static props = { ...standardActionServiceProps };
    static components = { Pager, Dropdown, DropdownItem, CheckBox };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            reports: [],
            reportKey: "",
            metadata: null,
            draftFilters: {},
            appliedFilters: {},
            optionLabels: {},
            filterOptions: {},
            sidebarOpen: true,
            rows: [],
            total: 0,
            offset: 0,
            limit: 80,
            sort: { key: "date", direction: "desc" },
            loading: true,
            exporting: false,
            selectedRows: [],
            allRowsSelected: false,
            selectAllMatching: false,
            error: "",
            mode: "fixed",
            dynamicModelKey: "",
            dynamicFields: [],
            selectedColumns: [],
            fieldsPickerOpen: false,
            multiRelationOptions: {},
            multiRelationSearch: {},
            openMultiRelation: null,
            downloadMenuOpen: false,
            favorites: [],
            savingFavorite: false,
            newFavoriteName: "",
            userInfo: null,
            generatedAt: null,
            visibleOptionalColumns: [],
        });
        this.requestSequence = 0;
        this.lookupTimers = {};
        for (const name of [
            "onReportChange", "onFilterInput", "onLookupFocus", "onLookupInput", "onLookupBlur",
            "selectLookupOption", "clearLookup", "applyFilters", "resetFilters", "toggleSidebar",
            "sortBy", "exportReport", "onPagerUpdate",
            "toggleRowSelection", "toggleAllRows", "clearSelection", "toggleDynamicColumn",
            "toggleFieldsPicker", "toggleMultiRelationPicker", "toggleMultiRelationValue",
            "toggleAllMultiRelation", "setMultiRelationSearch", "selectAllMatchingRecords",
            "toggleDownloadMenu", "onDownloadFormat", "applyFavorite", "removeFavorite",
            "startSaveFavorite", "onNewFavoriteNameInput", "onNewFavoriteKeydown", "confirmSaveFavorite", "cancelSaveFavorite",
            "toggleOptionalColumn",
        ]) {
            this[name] = this[name].bind(this);
        }
        onWillStart(() => this.loadReports());
    }

    async loadReports() {
        try {
            const [standardReports, dynamicModels, userInfo] = await Promise.all([
                this.orm.call("harleys.reports.service", "get_reports"),
                this.orm.call("harleys.reports.service", "get_dynamic_models"),
                this.orm.call("harleys.reports.service", "get_current_user_info"),
            ]);
            this.state.userInfo = userInfo;
            this.state.reports = [
                ...standardReports.map((report) => ({ ...report, group: "standard" })),
                ...dynamicModels.map((model) => ({
                    key: MODEL_KEY_PREFIX + model.model,
                    title: model.name,
                    group: "models",
                })),
            ];
            if (!this.state.reports.length) {
                this.state.error = "No reports are available for your access rights.";
                return;
            }
            const defaultReport = this.state.reports.find((report) => report.key === DEFAULT_REPORT_KEY) || this.state.reports[0];
            await this.selectReport(defaultReport.key);
        } catch (error) {
            this.showError(error, "Harleys Reports could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    async selectReport(reportKey) {
        if (reportKey.startsWith(MODEL_KEY_PREFIX)) {
            this.state.mode = "dynamic";
            this.state.reportKey = reportKey;
            await this.selectDynamicModel(reportKey.slice(MODEL_KEY_PREFIX.length));
            return;
        }
        this.state.loading = true;
        this.state.error = "";
        try {
            const metadata = await this.orm.call(
                "harleys.reports.service", "get_report_metadata", [reportKey]
            );
            this.state.mode = "fixed";
            this.state.reportKey = reportKey;
            this.state.metadata = metadata;
            this.state.draftFilters = { ...metadata.default_filters };
            this.state.appliedFilters = { ...metadata.default_filters };
            this.state.optionLabels = {};
            this.state.filterOptions = {};
            this.state.multiRelationOptions = {};
            this.state.multiRelationSearch = {};
            this.state.openMultiRelation = null;
            this.state.offset = 0;
            this.state.limit = metadata.default_page_size;
            this.state.sort = { ...metadata.default_sort };
            this.clearSelection();
            this.loadFavorites();
            this.loadOptionalColumns();
            await this.ensureMultiRelationDefaults();
            await this.fetchPage();
        } catch (error) {
            this.showError(error, "The selected report could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    async selectDynamicModel(modelKey) {
        this.state.loading = true;
        this.state.error = "";
        try {
            const modelMeta = await this.orm.call("harleys.reports.service", "get_dynamic_model_metadata", [modelKey]);
            this.state.dynamicModelKey = modelKey;
            this.state.dynamicFields = modelMeta.fields;
            this.state.selectedColumns = modelMeta.fields.slice(0, DYNAMIC_DEFAULT_COLUMN_COUNT).map((field) => field.name);
            this.state.draftFilters = {};
            this.state.appliedFilters = {};
            this.state.optionLabels = {};
            this.state.filterOptions = {};
            this.state.offset = 0;
            this.state.limit = DYNAMIC_DEFAULT_PAGE_SIZE;
            this.state.fieldsPickerOpen = false;
            const sortField = modelMeta.fields.find((field) => field.store) || modelMeta.fields[0];
            this.state.sort = { key: sortField.name, direction: "asc" };
            this.rebuildDynamicMetadata(modelMeta.fields, modelMeta.title, modelMeta.description);
            this.clearSelection();
            this.loadFavorites();
            await this.fetchPage();
        } catch (error) {
            this.showError(error, "The selected model could not be loaded.");
        } finally {
            this.state.loading = false;
        }
    }

    rebuildDynamicMetadata(fields, title, description) {
        const selected = fields.filter((field) => this.state.selectedColumns.includes(field.name));
        this.state.metadata = {
            key: this.state.reportKey,
            title,
            description,
            filters: selected.map((field) => this.describeDynamicFilter(field)),
            columns: selected.map((field) => ({
                key: field.name,
                label: field.label,
                type: field.type === "selection" ? "badge" : field.type === "numeric" ? "float" : "text",
                align: field.type === "numeric" ? "end" : undefined,
                sortable: field.store,
            })),
            default_filters: {},
            default_sort: { key: this.state.selectedColumns[0], direction: "asc" },
            page_sizes: DYNAMIC_PAGE_SIZES,
            default_page_size: DYNAMIC_DEFAULT_PAGE_SIZE,
            maximum_page_size: DYNAMIC_MAXIMUM_PAGE_SIZE,
            export_formats: ["csv", "xlsx"],
        };
    }

    describeDynamicFilter(field) {
        const base = { key: field.name, label: field.label, group: "primary" };
        if (field.type === "numeric") {
            return { ...base, type: "numeric_range", keyMin: `${field.name}__min`, keyMax: `${field.name}__max` };
        }
        if (field.type === "boolean") {
            return {
                ...base, type: "selection",
                options: [{ value: "", label: "All" }, { value: "true", label: "Yes" }, { value: "false", label: "No" }],
            };
        }
        if (field.type === "selection") {
            return { ...base, type: "selection", options: [{ value: "", label: "All" }, ...field.options] };
        }
        return { ...base, type: field.type };
    }

    toggleFieldsPicker() {
        this.state.fieldsPickerOpen = !this.state.fieldsPickerOpen;
    }

    async toggleDynamicColumn(fieldName) {
        const isSelected = this.state.selectedColumns.includes(fieldName);
        if (isSelected && this.state.selectedColumns.length === 1) {
            return;
        }
        const next = isSelected
            ? this.state.selectedColumns.filter((name) => name !== fieldName)
            : [...this.state.selectedColumns, fieldName];
        this.state.selectedColumns = this.state.dynamicFields
            .map((field) => field.name)
            .filter((name) => next.includes(name));
        this.rebuildDynamicMetadata(this.state.dynamicFields, this.state.metadata.title, this.state.metadata.description);
        if (!this.state.selectedColumns.includes(this.state.sort.key)) {
            this.state.sort = { key: this.state.selectedColumns[0], direction: "asc" };
        }
        this.state.offset = 0;
        await this.fetchPage();
    }

    async fetchPage() {
        const sequence = ++this.requestSequence;
        this.state.loading = true;
        this.state.error = "";
        try {
            const page = this.state.mode === "dynamic"
                ? await this.orm.call("harleys.reports.service", "get_dynamic_report_page", [
                      this.state.dynamicModelKey,
                      this.state.selectedColumns,
                      { ...this.state.appliedFilters },
                      this.state.offset,
                      this.state.limit,
                      { ...this.state.sort },
                  ])
                : await this.orm.call("harleys.reports.service", "get_report_page", [
                      this.state.reportKey,
                      { ...this.state.appliedFilters },
                      this.state.offset,
                      this.state.limit,
                      { ...this.state.sort },
                  ]);
            if (sequence !== this.requestSequence) {
                return;
            }
            this.state.rows = page.rows;
            this.state.total = page.total;
            this.state.offset = page.offset;
            this.state.selectedRows = this.state.selectedRows.filter((rowId) => page.rows.some((row) => row.id === rowId));
            this.state.allRowsSelected = this.state.rows.length > 0 && this.state.rows.every((row) => this.state.selectedRows.includes(row.id));
            this.state.generatedAt = Date.now();
        } catch (error) {
            if (sequence === this.requestSequence) {
                this.state.rows = [];
                this.state.total = 0;
                this.showError(error, "Report data could not be loaded.");
            }
        } finally {
            if (sequence === this.requestSequence) {
                this.state.loading = false;
            }
        }
    }

    onReportChange(event) {
        this.selectReport(event.target.value);
    }

    onFilterInput(filterKey, event) {
        this.state.draftFilters[filterKey] = event.target.value;
    }

    async fetchLookupOptions(filterKey, term) {
        try {
            this.state.filterOptions[filterKey] = this.state.mode === "dynamic"
                ? await this.orm.call(
                      "harleys.reports.service", "search_dynamic_filter_options",
                      [this.state.dynamicModelKey, filterKey, term, 20]
                  )
                : await this.orm.call(
                      "harleys.reports.service", "search_filter_options",
                      [this.state.reportKey, filterKey, term, 20]
                  );
        } catch (error) {
            this.showError(error, "Filter options could not be loaded.");
        }
    }

    onLookupFocus(filterKey) {
        this.fetchLookupOptions(filterKey, this.state.optionLabels[filterKey] || "");
    }

    onLookupInput(filterKey, event) {
        const term = event.target.value;
        this.state.optionLabels[filterKey] = term;
        delete this.state.draftFilters[filterKey];
        clearTimeout(this.lookupTimers[filterKey]);
        this.lookupTimers[filterKey] = setTimeout(() => this.fetchLookupOptions(filterKey, term), 250);
    }

    onLookupBlur(filterKey) {
        clearTimeout(this.lookupTimers[filterKey]);
        setTimeout(() => {
            this.state.filterOptions[filterKey] = [];
        }, 150);
    }

    selectLookupOption(filterKey, option) {
        this.state.draftFilters[filterKey] = option.id;
        this.state.optionLabels[filterKey] = option.label;
        this.state.filterOptions[filterKey] = [];
    }

    clearLookup(filterKey) {
        delete this.state.draftFilters[filterKey];
        delete this.state.optionLabels[filterKey];
        this.state.filterOptions[filterKey] = [];
    }

    async applyFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.state.offset = 0;
        this.clearSelection();
        await this.fetchPage();
    }

    async resetFilters() {
        this.state.draftFilters = { ...this.state.metadata.default_filters };
        this.state.appliedFilters = { ...this.state.metadata.default_filters };
        this.state.optionLabels = {};
        this.state.filterOptions = {};
        this.state.offset = 0;
        this.clearSelection();
        this.state.sort = { ...this.state.metadata.default_sort };
        await this.ensureMultiRelationDefaults();
        await this.fetchPage();
    }

    async ensureMultiRelationDefaults() {
        const filters = (this.state.metadata?.filters || []).filter((filter) => filter.type === "multi_relation");
        for (const filter of filters) {
            if (!this.state.multiRelationOptions[filter.key]) {
                await this.loadMultiRelationOptions(filter.key);
            }
            if (!(filter.key in this.state.draftFilters)) {
                const allIds = this.state.multiRelationOptions[filter.key].map((option) => option.id);
                this.state.draftFilters[filter.key] = allIds;
                this.state.appliedFilters[filter.key] = allIds;
            }
        }
    }

    async loadMultiRelationOptions(filterKey) {
        try {
            this.state.multiRelationOptions[filterKey] = this.state.mode === "dynamic"
                ? await this.orm.call("harleys.reports.service", "search_dynamic_filter_options", [this.state.dynamicModelKey, filterKey, "", 200])
                : await this.orm.call("harleys.reports.service", "search_filter_options", [this.state.reportKey, filterKey, "", 200]);
        } catch (error) {
            this.state.multiRelationOptions[filterKey] = [];
            this.showError(error, "Filter options could not be loaded.");
        }
    }

    toggleMultiRelationPicker(filterKey) {
        this.state.openMultiRelation = this.state.openMultiRelation === filterKey ? null : filterKey;
    }

    async toggleMultiRelationValue(filterKey, optionId) {
        const current = this.state.draftFilters[filterKey] || [];
        this.state.draftFilters[filterKey] = current.includes(optionId)
            ? current.filter((id) => id !== optionId)
            : [...current, optionId];
        await this.applyFilters();
    }

    setMultiRelationSearch(filterKey, event) {
        this.state.multiRelationSearch[filterKey] = event.target.value;
    }

    filteredMultiRelationOptions(filterKey) {
        const term = (this.state.multiRelationSearch[filterKey] || "").trim().toLowerCase();
        const options = this.state.multiRelationOptions[filterKey] || [];
        if (!term) {
            return options;
        }
        return options.filter((option) => option.label.toLowerCase().includes(term));
    }

    allMultiRelationVisibleSelected(filterKey) {
        const visibleIds = this.filteredMultiRelationOptions(filterKey).map((option) => option.id);
        const current = this.state.draftFilters[filterKey] || [];
        return visibleIds.length > 0 && visibleIds.every((id) => current.includes(id));
    }

    async toggleAllMultiRelation(filterKey) {
        const visibleIds = this.filteredMultiRelationOptions(filterKey).map((option) => option.id);
        const current = this.state.draftFilters[filterKey] || [];
        const allVisibleSelected = this.allMultiRelationVisibleSelected(filterKey);
        this.state.draftFilters[filterKey] = allVisibleSelected
            ? current.filter((id) => !visibleIds.includes(id))
            : Array.from(new Set([...current, ...visibleIds]));
        await this.applyFilters();
    }

    multiRelationSummary(filterKey) {
        const total = (this.state.multiRelationOptions[filterKey] || []).length;
        const selected = (this.state.draftFilters[filterKey] || []).length;
        const label = this.state.metadata?.filters?.find((filter) => filter.key === filterKey)?.label || "options";
        if (!total) {
            return "No options";
        }
        return selected === total ? `All ${total} ${label} selected` : `${selected} of ${total} ${label} selected`;
    }

    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    async sortBy(column) {
        if (!column.sortable || this.state.loading) {
            return;
        }
        const direction = this.state.sort.key === column.key && this.state.sort.direction === "asc"
            ? "desc" : "asc";
        this.state.sort = { key: column.key, direction };
        this.state.offset = 0;
        await this.fetchPage();
    }

    async onPagerUpdate({ offset, limit }) {
        this.state.offset = offset;
        this.state.limit = limit;
        await this.fetchPage();
    }

    async exportReport(format) {
        this.state.exporting = true;
        try {
            const row_ids = this.state.selectAllMatching
                ? null
                : (this.state.selectedRows.length ? this.state.selectedRows : null);
            const payload = this.state.mode === "dynamic"
                ? {
                      model_name: this.state.dynamicModelKey,
                      columns: this.state.selectedColumns,
                      filters: this.state.appliedFilters,
                      sort: this.state.sort,
                      row_ids,
                  }
                : {
                      report_key: this.state.reportKey,
                      filters: this.state.appliedFilters,
                      sort: this.state.sort,
                      row_ids,
                  };
            await download({
                url: `/harleys_reports/export/${format}`,
                data: { data: JSON.stringify(payload) },
            });
        } catch (error) {
            this.showError(error, `The ${format.toUpperCase()} export could not be generated.`);
        } finally {
            this.state.exporting = false;
        }
    }

    toggleDownloadMenu() {
        this.state.downloadMenuOpen = !this.state.downloadMenuOpen;
    }

    async onDownloadFormat(format) {
        this.state.downloadMenuOpen = false;
        await this.exportReport(format);
    }

    favoritesStorageKey() {
        return `harleys_reports.favorites.${this.state.reportKey}`;
    }

    loadFavorites() {
        let raw = null;
        try {
            raw = window.localStorage.getItem(this.favoritesStorageKey());
        } catch {
            raw = null;
        }
        if (raw) {
            this.state.favorites = JSON.parse(raw);
            return;
        }
        // First time this report is opened on this browser - seed a couple of sample
        // favorites so the feature is discoverable instead of showing an empty list.
        this.state.favorites = [
            { name: "This Month", filters: { ...this.state.appliedFilters } },
            { name: "My Usual View", filters: { ...this.state.appliedFilters } },
        ];
        this.persistFavorites();
    }

    persistFavorites() {
        window.localStorage.setItem(this.favoritesStorageKey(), JSON.stringify(this.state.favorites));
    }

    startSaveFavorite() {
        if (this.state.favorites.length >= MAX_FAVORITES) {
            return;
        }
        this.state.savingFavorite = true;
        this.state.newFavoriteName = "";
    }

    onNewFavoriteNameInput(event) {
        this.state.newFavoriteName = event.target.value;
    }

    onNewFavoriteKeydown(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            this.confirmSaveFavorite();
        } else if (event.key === "Escape") {
            this.cancelSaveFavorite();
        }
    }

    confirmSaveFavorite() {
        const name = this.state.newFavoriteName.trim();
        if (!name || this.state.favorites.length >= MAX_FAVORITES) {
            return;
        }
        this.state.favorites = [...this.state.favorites, { name, filters: { ...this.state.appliedFilters } }];
        this.persistFavorites();
        this.state.savingFavorite = false;
        this.state.newFavoriteName = "";
    }

    cancelSaveFavorite() {
        this.state.savingFavorite = false;
        this.state.newFavoriteName = "";
    }

    visibleColumnsStorageKey() {
        return `harleys_reports.visibleColumns.${this.state.reportKey}`;
    }

    loadOptionalColumns() {
        let raw = null;
        try {
            raw = window.localStorage.getItem(this.visibleColumnsStorageKey());
        } catch {
            raw = null;
        }
        // Every column is user-selectable, not just the ones flagged "optional" - that flag now
        // only decides what's checked the first time a user opens this report.
        this.state.visibleOptionalColumns = raw
            ? JSON.parse(raw)
            : (this.state.metadata?.columns || []).filter((column) => !column.optional).map((column) => column.key);
    }

    persistOptionalColumns() {
        window.localStorage.setItem(this.visibleColumnsStorageKey(), JSON.stringify(this.state.visibleOptionalColumns));
    }

    toggleOptionalColumn(columnKey) {
        const isVisible = this.state.visibleOptionalColumns.includes(columnKey);
        if (isVisible && this.state.visibleOptionalColumns.length === 1) {
            return;
        }
        this.state.visibleOptionalColumns = isVisible
            ? this.state.visibleOptionalColumns.filter((key) => key !== columnKey)
            : [...this.state.visibleOptionalColumns, columnKey];
        this.persistOptionalColumns();
    }

    get optionalColumns() {
        return this.state.metadata?.columns || [];
    }

    get displayColumns() {
        return (this.state.metadata?.columns || []).filter(
            (column) => this.state.visibleOptionalColumns.includes(column.key)
        );
    }

    async applyFavorite(favorite) {
        this.state.draftFilters = { ...favorite.filters };
        this.state.appliedFilters = { ...favorite.filters };
        this.state.offset = 0;
        await this.fetchPage();
    }

    removeFavorite(index, event) {
        event.stopPropagation();
        this.state.favorites = this.state.favorites.filter((_, favoriteIndex) => favoriteIndex !== index);
        this.persistFavorites();
    }

    toggleRowSelection(rowId) {
        if (this.state.selectAllMatching) {
            // Narrowing from "every matching record" to "every row on this page except this
            // one" is the only sensible degradation without knowing the full matching id set.
            this.state.selectAllMatching = false;
            this.state.selectedRows = this.state.rows.map((row) => row.id).filter((id) => id !== rowId);
            this.state.allRowsSelected = this.state.rows.length > 1;
            return;
        }
        const exists = this.state.selectedRows.includes(rowId);
        this.state.selectedRows = exists
            ? this.state.selectedRows.filter((id) => id !== rowId)
            : [...this.state.selectedRows, rowId];
        this.state.allRowsSelected = this.state.rows.length > 0 && this.state.rows.every((row) => this.state.selectedRows.includes(row.id));
    }

    toggleAllRows() {
        this.state.selectAllMatching = false;
        if (!this.state.rows.length) {
            this.state.selectedRows = [];
            this.state.allRowsSelected = false;
            return;
        }
        if (this.state.allRowsSelected) {
            this.state.selectedRows = this.state.selectedRows.filter((rowId) => !this.state.rows.some((row) => row.id === rowId));
            this.state.allRowsSelected = false;
            return;
        }
        const rowIds = this.state.rows.map((row) => row.id);
        this.state.selectedRows = Array.from(new Set([...this.state.selectedRows, ...rowIds]));
        this.state.allRowsSelected = true;
    }

    selectAllMatchingRecords() {
        this.state.selectAllMatching = true;
    }

    clearSelection() {
        this.state.selectedRows = [];
        this.state.allRowsSelected = false;
        this.state.selectAllMatching = false;
    }

    get selectionCount() {
        return this.state.selectAllMatching ? this.state.total : this.state.selectedRows.length;
    }

    get hasSelection() {
        return this.state.selectAllMatching || this.state.selectedRows.length > 0;
    }

    get pageLabel() {
        if (!this.state.total) {
            return "";
        }
        const pageCount = Math.max(1, Math.ceil(this.state.total / this.state.limit));
        const pageNumber = Math.floor(this.state.offset / this.state.limit) + 1;
        return `Page ${pageNumber} of ${pageCount}`;
    }

    get generatedAtLabel() {
        if (!this.state.generatedAt) {
            return "";
        }
        return `Generated ${new Date(this.state.generatedAt).toLocaleString()}`;
    }

    get showSelectAllMatchingPrompt() {
        return this.state.allRowsSelected && !this.state.selectAllMatching && this.state.total > this.state.rows.length;
    }

    showError(error, fallback) {
        const message = error?.data?.message || error?.message || fallback;
        this.state.error = message;
        this.notification.add(message, { title: "Harleys Reports", type: "danger" });
    }

    get standardReports() {
        return this.state.reports.filter((report) => report.group === "standard");
    }

    get modelReports() {
        return this.state.reports.filter((report) => report.group === "models");
    }

    get primaryFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.group === "primary" && !filter.hidden);
    }

    get advancedFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.group === "advanced" && !filter.hidden);
    }

    get visibleFilters() {
        return this.primaryFilters.concat(this.advancedFilters);
    }

    optionLabel(columnKey, value) {
        const filter = this.state.metadata?.filters?.find((item) => item.key === columnKey);
        const filterOption = filter?.options?.find((item) => item.value === value);
        if (filterOption) {
            return filterOption.label;
        }
        const column = this.state.metadata?.columns?.find((item) => item.key === columnKey);
        return column?.options?.find((item) => item.value === value)?.label ?? value;
    }

    badgeClass(value) {
        return {
            done: "text-bg-success", posted: "text-bg-success", sale: "text-bg-success",
            purchase: "text-bg-success", paid: "text-bg-success",
            cancel: "text-bg-danger", not_paid: "text-bg-danger",
            assigned: "text-bg-info", sent: "text-bg-info", in_payment: "text-bg-info",
            draft: "text-bg-secondary",
            waiting: "text-bg-warning", confirmed: "text-bg-warning",
            partially_available: "text-bg-warning", partial: "text-bg-warning",
            pending: "text-bg-warning",
        }[value] || "text-bg-secondary";
    }
}

registry.category("actions").add("harleys_reports.app", HarleysReportsApp);
