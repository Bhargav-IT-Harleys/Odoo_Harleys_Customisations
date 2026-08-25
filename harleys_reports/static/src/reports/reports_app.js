import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Pager } from "@web/core/pager/pager";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";

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
            rows: [],
            groups: [],
            expandedLocations: {},
            expandedDates: {},
            total: 0,
            offset: 0,
            limit: 80,
            sort: { key: "date", direction: "desc" },
            loading: true,
            exporting: false,
            selectedRows: [],
            selectAllMatching: false,
            error: "",
            mode: "fixed",
            dynamicModelKey: "",
            dynamicFields: [],
            selectedColumns: [],
            multiRelationOptions: {},
            multiRelationSearch: {},
            openMultiRelation: null,
            sidebarCollapsed: false,
            globalSearchTerm: "",
            globalSearchResults: {},
            globalSearchExpanded: null,
            globalSearchLoading: false,
            favorites: [],
            savingFavorite: false,
            newFavoriteName: "",
            userInfo: null,
            generatedAt: null,
            visibleOptionalColumns: [],
            hasSearched: false,
        });
        this.requestSequence = 0;
        this.lookupTimers = {};
        this.globalSearchDropdown = useDropdownState();
        this.globalSearchTimer = null;
        this.globalSearchSequence = 0;
        for (const name of [
            "onFilterInput", "onLookupFocus", "onLookupInput", "onLookupBlur",
            "selectLookupOption", "clearLookup", "applyFilters", "resetFilters",
            "sortBy", "exportReport", "onPagerUpdate",
            "toggleRowSelection", "toggleAllRows", "clearSelection", "toggleDynamicColumn",
            "toggleMultiRelationValue",
            "toggleAllMultiRelation", "setMultiRelationSearch", "selectAllMatchingRecords",
            "toggleMultiRelationPicker",
            "onDownloadFormat", "applyFavorite", "removeFavorite",
            "startSaveFavorite", "onNewFavoriteNameInput", "onNewFavoriteKeydown", "confirmSaveFavorite", "cancelSaveFavorite",
            "toggleOptionalColumn", "toggleSidebar", "toggleLocationGroup", "toggleDateGroup",
            "onGlobalSearchInput", "onGlobalSearchFocus", "onGlobalSearchBlur",
            "toggleGlobalSearchGroup", "selectGlobalSearchOption",
            "applyGlobalSearchText", "selectGlobalSearchSelectionOption", "applyGlobalSearchDate",
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
            // Each menu entry (Stock Report, Move History, ...) is its own ir.actions.client
            // pointed at this same component, differing only by this param - falls back to the
            // generic "Report Extraction" action's default when launched without one.
            const requestedKey = this.props.action?.params?.report_key;
            const defaultReport = this.state.reports.find((report) => report.key === requestedKey)
                || this.state.reports.find((report) => report.key === DEFAULT_REPORT_KEY)
                || this.state.reports[0];
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
            this.resetGlobalSearch();
            this.state.offset = 0;
            this.state.limit = metadata.default_page_size;
            this.state.sort = { ...metadata.default_sort };
            this.state.expandedLocations = {};
            this.state.expandedDates = {};
            this.clearSelection();
            this.loadFavorites();
            this.loadOptionalColumns();
            await this.ensureMultiRelationDefaults();
            // Doesn't auto-fetch - reports gated on a required_for_search filter (Warehouses)
            // start on the blank "select a warehouse" prompt instead of loading everything, see
            // canSearch/_commitAppliedFilters.
            await this._commitAppliedFilters();
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
            this.resetGlobalSearch();
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

    // Location -> Date collapsible groups (Physical Inventory) need the full matching set at
    // once to compute accurate counts/totals per group, not a row-count-based page - see
    // get_grouped_rows on the backend. state.rows keeps the flattened full set (still needed by
    // export/selectAllMatching, which operate on "every matching record" regardless of what's
    // expanded); the header checkbox and "select all" instead work off visibleRows, which is
    // just the currently-expanded subset - see toggleAllRows.
    async fetchGroupedRows() {
        const sequence = ++this.requestSequence;
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("harleys.reports.service", "get_report_grouped_rows", [
                this.state.reportKey,
                { ...this.state.appliedFilters },
                { ...this.state.sort },
            ]);
            if (sequence !== this.requestSequence) {
                return;
            }
            const rows = result.groups.flatMap((location) => location.groups.flatMap((dateGroup) => dateGroup.rows));
            this.state.groups = result.groups;
            this.state.rows = rows;
            this.state.total = result.total;
            this.state.offset = 0;
            this.state.limit = result.total || this.state.limit;
            this.state.selectedRows = this.state.selectedRows.filter((rowId) => rows.some((row) => row.id === rowId));
            this.state.generatedAt = Date.now();
        } catch (error) {
            if (sequence === this.requestSequence) {
                this.state.groups = [];
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

    async fetchPage() {
        if (this.state.mode === "fixed" && this.state.metadata?.grouped) {
            await this.fetchGroupedRows();
            return;
        }
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

    // The only filter types still routed here (date, selection) fire once per complete value,
    // not per keystroke, so auto-applying is safe - there's no separate global Apply button
    // anymore, every filter mechanism now commits itself.
    async onFilterInput(filterKey, event) {
        this.state.draftFilters[filterKey] = event.target.value;
        await this.applyFilters();
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

    // A "text + lookup" filter (e.g. Product/SKU search) stores the picked label itself as the
    // filter value, so the backend's existing ilike-substring match still applies - it's the
    // same filter mechanism as before, just committed on selection instead of on every
    // keystroke. A real many2one filter stores the record id instead.
    async selectLookupOption(filterKey, option) {
        const filter = this.state.metadata?.filters?.find((item) => item.key === filterKey);
        this.state.draftFilters[filterKey] = filter?.type === "text" ? option.label : option.id;
        this.state.optionLabels[filterKey] = option.label;
        this.state.filterOptions[filterKey] = [];
        await this.applyFilters();
    }

    clearLookup(filterKey) {
        delete this.state.draftFilters[filterKey];
        delete this.state.optionLabels[filterKey];
        this.state.filterOptions[filterKey] = [];
    }

    // Filters flagged required_for_search (Warehouses, on every current report) must have a
    // real selection in draftFilters before anything is fetched - this is the single gate
    // shared by the "Apply Filters" button's disabled state and every path that commits
    // filters (see _commitAppliedFilters). Vacuously true for reports with no such filter
    // (dynamic model browsers), so it never blocks them.
    get gateFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.required_for_search);
    }

    get gateFiltersLabel() {
        return this.gateFilters.map((filter) => filter.label).join(" / ");
    }

    get canSearch() {
        return this.gateFilters.every((filter) => {
            const value = this.state.draftFilters[filter.key];
            return Array.isArray(value) ? value.length > 0 : !!value;
        });
    }

    // Single commit point for every "apply the staged filters" action - the shared Apply
    // Filters button, Reset Filters, and the initial report load all route through this so the
    // canSearch gate (and the resulting blank-state prompt) behaves identically everywhere.
    async _commitAppliedFilters() {
        this.state.appliedFilters = { ...this.state.draftFilters };
        this.state.offset = 0;
        this.state.expandedLocations = {};
        this.state.expandedDates = {};
        this.clearSelection();
        if (!this.canSearch) {
            this.state.hasSearched = false;
            this.state.groups = [];
            this.state.rows = [];
            this.state.total = 0;
            return;
        }
        this.state.hasSearched = true;
        await this.fetchPage();
    }

    async applyFilters() {
        await this._commitAppliedFilters();
    }

    async resetFilters() {
        this.state.draftFilters = { ...this.state.metadata.default_filters };
        this.state.appliedFilters = { ...this.state.metadata.default_filters };
        this.state.optionLabels = {};
        this.state.filterOptions = {};
        this.state.sort = { ...this.state.metadata.default_sort };
        await this.ensureMultiRelationDefaults();
        await this._commitAppliedFilters();
    }

    async ensureMultiRelationDefaults() {
        const filters = (this.state.metadata?.filters || []).filter((filter) => filter.type === "multi_relation");
        for (const filter of filters) {
            if (!this.state.multiRelationOptions[filter.key]) {
                await this.loadMultiRelationOptions(filter.key);
            }
            if (!(filter.key in this.state.draftFilters)) {
                const options = this.state.multiRelationOptions[filter.key];
                // Filters gated for search (Warehouses) start empty - the user must
                // deliberately pick at least one before anything loads (see canSearch).
                // Non-gated multi-relation filters still default to "select everything", unless
                // they opt out via default_select:"first".
                const defaultIds = filter.required_for_search
                    ? []
                    : filter.default_select === "first"
                        ? options.slice(0, 1).map((option) => option.id)
                        : options.map((option) => option.id);
                this.state.draftFilters[filter.key] = defaultIds;
                this.state.appliedFilters[filter.key] = defaultIds;
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

    // Stages the change only - checking several boxes in a row shouldn't fire a fetch per
    // click. The shared "Apply Filters" button (see applyFilters) is what commits it.
    toggleMultiRelationValue(filterKey, optionId) {
        const current = this.state.draftFilters[filterKey] || [];
        this.state.draftFilters[filterKey] = current.includes(optionId)
            ? current.filter((id) => id !== optionId)
            : [...current, optionId];
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

    toggleAllMultiRelation(filterKey) {
        const visibleIds = this.filteredMultiRelationOptions(filterKey).map((option) => option.id);
        const current = this.state.draftFilters[filterKey] || [];
        const allVisibleSelected = this.allMultiRelationVisibleSelected(filterKey);
        this.state.draftFilters[filterKey] = allVisibleSelected
            ? current.filter((id) => !visibleIds.includes(id))
            : Array.from(new Set([...current, ...visibleIds]));
    }

    // Dropdown is collapsed by default and toggled with a plain click (no focus/blur tricks -
    // those caused real bugs before). Only one open at a time keeps it simple.
    toggleMultiRelationPicker(filterKey) {
        this.state.openMultiRelation = this.state.openMultiRelation === filterKey ? null : filterKey;
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

    // Multi-relation filters (Warehouses, Categories, Product Type) get their own always-visible
    // checklist section in the sidebar, same idea as the Location panel in Odoo's own Physical
    // Inventory screen - never hidden behind a popover that has to be found and opened.
    get multiRelationFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.type === "multi_relation" && !filter.hidden);
    }

    // Every non-hidden filter on the current report gets a Quick Search group - not just
    // relational ones. Each group's expanded content branches by filter.type in the template:
    // multi_relation/many2one/lookup-text show fetched suggestions (see
    // globalSearchLookupFilters below), selection filters match against their own static
    // options client-side, date filters get an inline date input, and plain text filters let
    // you apply the typed term directly - see applyGlobalSearchText/
    // selectGlobalSearchSelectionOption/applyGlobalSearchDate.
    get eligibleGlobalSearchFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => !filter.hidden);
    }

    // Subset that actually needs a fetched/cached suggestion list - the other filter types
    // (selection, date, plain text) render their own content directly from
    // state.globalSearchTerm or the filter's own static options, no fetch involved.
    get globalSearchLookupFilters() {
        return this.eligibleGlobalSearchFilters.filter((filter) =>
            filter.type === "multi_relation" || filter.type === "many2one" || filter.lookup === true
        );
    }

    // Client-side match against a selection filter's own embedded options (same options array
    // already used by the sidebar's plain <select>) - excludes the blank "All" option, which
    // isn't a meaningful quick-search result.
    filteredSelectionOptions(filter) {
        const term = (this.state.globalSearchTerm || "").trim().toLowerCase();
        const options = (filter.options || []).filter((option) => option.value !== "");
        if (!term) {
            return options;
        }
        return options.filter((option) => option.label.toLowerCase().includes(term));
    }

    onGlobalSearchInput(event) {
        const term = event.target.value;
        this.state.globalSearchTerm = term;
        this.state.globalSearchExpanded = null;
        clearTimeout(this.globalSearchTimer);
        if (!term.trim()) {
            this.state.globalSearchResults = {};
            this.globalSearchDropdown.close();
            return;
        }
        this.globalSearchDropdown.open();
        this.globalSearchTimer = setTimeout(() => this.fetchGlobalSearchResults(term), 250);
    }

    onGlobalSearchFocus() {
        if (this.state.globalSearchTerm.trim()) {
            this.globalSearchDropdown.open();
        }
    }

    onGlobalSearchBlur() {
        clearTimeout(this.globalSearchTimer);
        setTimeout(() => this.globalSearchDropdown.close(), 150);
    }

    // multi_relation options are filtered client-side out of the cache every multi-select
    // filter already loads once per report (loadMultiRelationOptions) - only lookup/many2one
    // filters need a live server round trip.
    async fetchGlobalSearchResults(term) {
        const sequence = ++this.globalSearchSequence;
        this.state.globalSearchLoading = true;
        try {
            const entries = await Promise.all(this.globalSearchLookupFilters.map(async (filter) => {
                if (filter.type === "multi_relation") {
                    const termLower = term.toLowerCase();
                    const options = (this.state.multiRelationOptions[filter.key] || [])
                        .filter((option) => option.label.toLowerCase().includes(termLower))
                        .slice(0, 5);
                    return [filter.key, options];
                }
                const options = this.state.mode === "dynamic"
                    ? await this.orm.call("harleys.reports.service", "search_dynamic_filter_options",
                          [this.state.dynamicModelKey, filter.key, term, 5])
                    : await this.orm.call("harleys.reports.service", "search_filter_options",
                          [this.state.reportKey, filter.key, term, 5]);
                return [filter.key, options];
            }));
            if (sequence !== this.globalSearchSequence) {
                return;
            }
            this.state.globalSearchResults = Object.fromEntries(entries);
        } catch (error) {
            if (sequence === this.globalSearchSequence) {
                this.showError(error, "Search suggestions could not be loaded.");
            }
        } finally {
            if (sequence === this.globalSearchSequence) {
                this.state.globalSearchLoading = false;
            }
        }
    }

    toggleGlobalSearchGroup(filterKey) {
        this.state.globalSearchExpanded = this.state.globalSearchExpanded === filterKey ? null : filterKey;
    }

    // Shared cleanup after any Quick Search pick, regardless of filter type - resets the search
    // box and closes the dropdown so the next open starts fresh.
    resetGlobalSearch() {
        this.state.globalSearchTerm = "";
        this.state.globalSearchResults = {};
        this.state.globalSearchExpanded = null;
        this.globalSearchDropdown.close();
    }

    // Same commit semantics as selectLookupOption/toggleMultiRelationValue - writing straight
    // into draftFilters means the sidebar's own controls (summary label, checkboxes) stay in
    // sync for free, no separate state to maintain.
    async selectGlobalSearchOption(filter, option) {
        if (filter.type === "multi_relation") {
            const current = this.state.draftFilters[filter.key] || [];
            if (!current.includes(option.id)) {
                this.state.draftFilters[filter.key] = [...current, option.id];
            }
        } else {
            this.state.draftFilters[filter.key] = filter.type === "text" ? option.label : option.id;
            this.state.optionLabels[filter.key] = option.label;
        }
        this.resetGlobalSearch();
        await this.applyFilters();
    }

    // Plain text filters (no lookup, e.g. a free-text Reference field) have no suggestion model
    // to query - Quick Search just applies whatever's typed directly, same ilike semantics
    // onFilterInput already uses for that filter in the sidebar.
    async applyGlobalSearchText(filter) {
        this.state.draftFilters[filter.key] = this.state.globalSearchTerm;
        this.resetGlobalSearch();
        await this.applyFilters();
    }

    // Selection options come from the filter's own static list (option.value/option.label),
    // not a fetched {id,label} pair like relational results - a distinct shape from
    // selectGlobalSearchOption above.
    async selectGlobalSearchSelectionOption(filter, option) {
        this.state.draftFilters[filter.key] = option.value;
        this.resetGlobalSearch();
        await this.applyFilters();
    }

    async applyGlobalSearchDate(filter, event) {
        this.state.draftFilters[filter.key] = event.target.value;
        this.resetGlobalSearch();
        await this.applyFilters();
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

    async onDownloadFormat(format) {
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

    // Location and Date are already shown on their own group headers when grouped - repeating
    // them on every row underneath would just be visual noise.
    get groupedDisplayColumns() {
        return this.displayColumns.filter((column) => column.key !== "location" && column.key !== "date");
    }

    get visibleTableColumns() {
        return this.state.metadata?.grouped ? this.groupedDisplayColumns : this.displayColumns;
    }

    // Same idea as Odoo's own grouped list views: the header "select all" checkbox only ever
    // reaches rows that are actually expanded/rendered right now, not every matching record
    // (that's what the separate "Select all N matching records" prompt is for). In flat/paginated
    // reports every row on the page is already "expanded", so this is just state.rows there.
    get visibleRows() {
        if (!(this.state.mode === "fixed" && this.state.metadata?.grouped)) {
            return this.state.rows;
        }
        const rows = [];
        for (const location of this.state.groups) {
            if (!this.isLocationExpanded(location.key)) {
                continue;
            }
            for (const dateGroup of location.groups) {
                if (this.isDateGroupExpanded(location.key, dateGroup.key)) {
                    rows.push(...dateGroup.rows);
                }
            }
        }
        return rows;
    }

    get allRowsSelected() {
        return this.visibleRows.length > 0 && this.visibleRows.every((row) => this.state.selectedRows.includes(row.id));
    }

    toggleLocationGroup(key) {
        this.state.expandedLocations = { ...this.state.expandedLocations, [key]: !this.state.expandedLocations[key] };
    }

    toggleDateGroup(locationKey, dateKey) {
        const key = `${locationKey}||${dateKey}`;
        this.state.expandedDates = { ...this.state.expandedDates, [key]: !this.state.expandedDates[key] };
    }

    isLocationExpanded(key) {
        return !!this.state.expandedLocations[key];
    }

    isDateGroupExpanded(locationKey, dateKey) {
        return !!this.state.expandedDates[`${locationKey}||${dateKey}`];
    }

    async applyFavorite(favorite) {
        // Merge on top of the report's current defaults, not a wholesale replace - a favorite
        // saved before a filter existed (e.g. ADU Visibility) has no key for it at all, and a
        // plain replace would leave that filter blank/undefined instead of at its real default.
        const base = this.state.metadata?.default_filters || {};
        this.state.draftFilters = { ...base, ...favorite.filters };
        this.state.appliedFilters = { ...base, ...favorite.filters };
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
            // Narrowing from "every matching record" to "every currently visible row except
            // this one" is the only sensible degradation without knowing the full matching id set.
            this.state.selectAllMatching = false;
            this.state.selectedRows = this.visibleRows.map((row) => row.id).filter((id) => id !== rowId);
            return;
        }
        const exists = this.state.selectedRows.includes(rowId);
        this.state.selectedRows = exists
            ? this.state.selectedRows.filter((id) => id !== rowId)
            : [...this.state.selectedRows, rowId];
    }

    toggleAllRows() {
        this.state.selectAllMatching = false;
        const visibleRows = this.visibleRows;
        if (!visibleRows.length) {
            this.state.selectedRows = [];
            return;
        }
        if (this.allRowsSelected) {
            this.state.selectedRows = this.state.selectedRows.filter((rowId) => !visibleRows.some((row) => row.id === rowId));
            return;
        }
        const rowIds = visibleRows.map((row) => row.id);
        this.state.selectedRows = Array.from(new Set([...this.state.selectedRows, ...rowIds]));
    }

    selectAllMatchingRecords() {
        this.state.selectAllMatching = true;
    }

    clearSelection() {
        this.state.selectedRows = [];
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
        return this.allRowsSelected && !this.state.selectAllMatching && this.state.total > this.visibleRows.length;
    }

    showError(error, fallback) {
        const message = error?.data?.message || error?.message || fallback;
        this.state.error = message;
        this.notification.add(message, { title: "Harleys Reports", type: "danger" });
    }

    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
    }

    get primaryFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.group === "primary" && !filter.hidden);
    }

    get advancedFilters() {
        return (this.state.metadata?.filters || []).filter((filter) => filter.group === "advanced" && !filter.hidden);
    }

    get visibleFilters() {
        // multi_relation filters get their own dedicated checklist section instead (see
        // multiRelationFilters), and quick_search_only filters are only reachable through the
        // unified Quick Search bar (so a report doesn't end up with two separate search boxes
        // for the same filter) - everything else (date, text, selection, many2one) renders
        // through the plain FilterFields inputs below.
        return this.primaryFilters.concat(this.advancedFilters).filter(
            (filter) => filter.type !== "multi_relation" && !filter.quick_search_only
        );
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

    // A fixed decimal count (e.g. 2) can crush a genuinely nonzero-but-tiny value (a daily
    // usage rate like 0.0004) down to a misleading "0.00" - values under 1 get enough
    // significant digits to always stay visibly nonzero, larger ones stay compact.
    formatFloat(value) {
        if (value === null || value === undefined || value === "") {
            return "";
        }
        const num = Number(value);
        if (!Number.isFinite(num) || num === 0) {
            return "0";
        }
        if (Math.abs(num) < 1) {
            return num.toPrecision(4).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
        }
        return num.toFixed(2);
    }
}

registry.category("actions").add("harleys_reports.app", HarleysReportsApp);
