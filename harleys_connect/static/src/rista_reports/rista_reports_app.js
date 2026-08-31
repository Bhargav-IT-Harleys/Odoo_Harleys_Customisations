import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class RistaReportsApp extends Component {
    static template = "harleys_connect.RistaReportsApp";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            catalog: [],
            reportId: "",
            paramValues: {},
            columns: [],
            rows: [],
            loading: false,
            error: "",
            hasSearched: false,
        });

        onWillStart(async () => {
            this.state.catalog = await this.orm.call(
                "harleys_connect.rista.service", "get_rista_catalog", []
            );
            if (this.state.catalog.length) {
                this.selectReport(this.state.catalog[0].id);
            }
        });
    }

    get selectedReport() {
        return this.state.catalog.find((report) => report.id === this.state.reportId);
    }

    selectReport(reportId) {
        this.state.reportId = reportId;
        this.state.paramValues = {};
        this.state.columns = [];
        this.state.rows = [];
        this.state.error = "";
        this.state.hasSearched = false;
    }

    onReportChange(ev) {
        this.selectReport(ev.target.value);
    }

    onParamInput(paramKey, ev) {
        this.state.paramValues[paramKey] = ev.target.value;
    }

    async fetchReport() {
        this.state.loading = true;
        this.state.error = "";
        try {
            const result = await this.orm.call(
                "harleys_connect.rista.service",
                "get_rista_report",
                [this.state.reportId, this.state.paramValues],
            );
            this.state.columns = result.columns;
            this.state.rows = result.rows;
            this.state.hasSearched = true;
        } catch (error) {
            this.state.columns = [];
            this.state.rows = [];
            this.state.hasSearched = true;
            this.state.error = (error && error.data && error.data.message) || "Failed to fetch report.";
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("harleys_connect.rista_reports_app", RistaReportsApp);
