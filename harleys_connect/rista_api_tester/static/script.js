document.addEventListener("DOMContentLoaded", () => {
    const els = {
        configStatus: document.getElementById("config-status"),
        btnGenerateJwt: document.getElementById("btn-generate-jwt"),
        jwtApiKey: document.getElementById("jwt-api-key"),
        jwtSecretKey: document.getElementById("jwt-secret-key"),
        jwtMethod: document.getElementById("jwt-method"),
        jwtResult: document.getElementById("jwt-result"),
        jwtOutput: document.getElementById("jwt-output"),
        btnCopyJwt: document.getElementById("btn-copy-jwt"),
        jwtError: document.getElementById("jwt-error"),
        testMethod: document.getElementById("test-method"),
        testPath: document.getElementById("test-path"),
        testQuery: document.getElementById("test-query"),
        btnSendRequest: document.getElementById("btn-send-request"),
        testResult: document.getElementById("test-result"),
        testStatus: document.getElementById("test-status"),
        testTime: document.getElementById("test-time"),
        testResponse: document.getElementById("test-response"),
        btnCopyResponse: document.getElementById("btn-copy-response"),
        btnExportExcel: document.getElementById("btn-export-excel"),
        testError: document.getElementById("test-error"),
        runMethod: document.getElementById("run-method"),
        runPath: document.getElementById("run-path"),
        runMode: document.getElementById("run-mode"),
        endpointSuggestions: document.getElementById("endpoint-suggestions"),
        commonRequest: document.getElementById("common-request"),
        btnExecute: document.getElementById("btn-execute"),
        executeProgress: document.getElementById("execute-progress"),
        composerError: document.getElementById("composer-error"),
        composerResults: document.getElementById("composer-results"),
        workflowSummary: document.getElementById("workflow-summary"),
        singleIterateControls: document.getElementById("single-iterate-controls"),
        customReportControls: document.getElementById("custom-report-controls"),
        apiSalesSummary: document.getElementById("api-sales-summary"),
        apiDiscountTransactions: document.getElementById("api-discount-transactions"),
        reportStartDate: document.getElementById("report-start-date"),
        reportEndDate: document.getElementById("report-end-date"),
        reportRequestData: document.getElementById("report-request-data"),
    };

    let apiCatalog = { apis: [] };

    function setError(container, message) {
        container.textContent = message;
        container.classList.remove("hidden");
    }

    function clearError(container) {
        container.textContent = "";
        container.classList.add("hidden");
    }

    async function loadConfig() {
        try {
            const res = await fetch("/api/config");
            const data = await res.json();
            const configured = data.configured;

            const apiStatus = data.api_key_configured
                ? `<strong>Configured</strong> <span class="mono">${data.api_key_masked || "****"}</span>`
                : '<strong class="missing">Missing</strong>';
            const secretStatus = data.secret_key_configured
                ? "<strong>Configured</strong>"
                : '<strong class="missing">Missing</strong>';

            els.configStatus.innerHTML = `
                <div class="config-row"><span>Rista API Key:</span> ${apiStatus}</div>
                <div class="config-row"><span>Rista Secret Key:</span> ${secretStatus}</div>
                <div class="config-row"><span>Rista Base URL:</span> <span class="mono">${data.base_url}</span></div>
                ${!configured ? '<p class="missing-notice">Paste credentials in the JWT Generator below, or configure RISTA_API_KEY and RISTA_SECRET_KEY in .env.</p>' : ""}
            `;
        } catch (exc) {
            els.configStatus.innerHTML = `<p class="error">Failed to load configuration: ${exc.message}</p>`;
        }
    }

    async function loadCatalog() {
        try {
            const res = await fetch("/api/catalog");
            apiCatalog = await res.json();
            populateEndpointSuggestions(apiCatalog.apis);
        } catch (exc) {
            setError(els.composerError, `Failed to load API catalog: ${exc.message}`);
        }
    }

    function populateEndpointSuggestions(apis) {
        const seen = new Set();
        const options = [];
        for (const api of apis) {
            if (api.type === "api" && api.path) {
                const path = api.path.startsWith("/") ? api.path : "/" + api.path;
                if (!seen.has(path)) {
                    seen.add(path);
                    options.push(path);
                }
            }
        }
        options.sort();
        els.endpointSuggestions.innerHTML = options.map(p => `<option value="${escapeHtml(p)}">`).join("");
    }

    function updateComposerMode() {
        const mode = els.runMode.value;
        if (mode === "custom_report") {
            els.singleIterateControls.classList.add("hidden");
            els.customReportControls.classList.remove("hidden");
        } else {
            els.singleIterateControls.classList.remove("hidden");
            els.customReportControls.classList.add("hidden");
        }
    }

    els.runMode.addEventListener("change", updateComposerMode);
    updateComposerMode();

    function escapeHtml(text) {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return text.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/'/g, "&#39;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    els.btnGenerateJwt.addEventListener("click", async () => {
        clearError(els.jwtError);
        els.jwtResult.classList.add("hidden");
        els.jwtOutput.value = "";

        const body = {
            method: els.jwtMethod.value,
            api_key: els.jwtApiKey.value.trim(),
            secret_key: els.jwtSecretKey.value.trim(),
        };

        try {
            const res = await fetch("/api/generate-token", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            if (!res.ok || !data.success) {
                setError(els.jwtError, data.error || "Failed to generate JWT.");
                return;
            }

            els.jwtOutput.value = data.token;
            els.jwtResult.classList.remove("hidden");
        } catch (exc) {
            setError(els.jwtError, `Network error: ${exc.message}`);
        }
    });

    els.btnCopyJwt.addEventListener("click", () => {
        if (!els.jwtOutput.value) return;
        navigator.clipboard.writeText(els.jwtOutput.value).then(() => {
            const original = els.btnCopyJwt.textContent;
            els.btnCopyJwt.textContent = "Copied!";
            setTimeout(() => { els.btnCopyJwt.textContent = original; }, 1500);
        });
    });

    els.btnSendRequest.addEventListener("click", async () => {
        clearError(els.testError);
        els.testResult.classList.add("hidden");
        els.testResponse.value = "";

        const path = els.testPath.value.trim();
        if (!path) {
            setError(els.testError, "Endpoint path is required.");
            return;
        }

        const body = {
            method: els.testMethod.value,
            path: path,
            api_key: els.jwtApiKey.value.trim(),
            secret_key: els.jwtSecretKey.value.trim(),
            query: els.testQuery.value.trim(),
        };

        try {
            const res = await fetch("/api/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });
            const data = await res.json();

            els.testResult.classList.remove("hidden");

            if (!data.success) {
                els.testStatus.textContent = `Error ${data.status_code || "N/A"}`;
                els.testStatus.className = "status error";
                els.testTime.textContent = data.response_time_ms ? `${data.response_time_ms}ms` : "";
                setError(els.testError, data.error || "Request failed.");
                return;
            }

            els.testStatus.textContent = `HTTP ${data.status_code}`;
            els.testStatus.className = data.status_code >= 400 ? "status error" : "status success";
            els.testTime.textContent = data.response_time_ms ? `${data.response_time_ms}ms` : "";

            const formatted = typeof data.response === "string"
                ? data.response
                : JSON.stringify(data.response, null, 2);
            els.testResponse.value = formatted;
        } catch (exc) {
            setError(els.testError, `Network error: ${exc.message}`);
        }
    });

    els.btnCopyResponse.addEventListener("click", () => {
        if (!els.testResponse.value) return;
        navigator.clipboard.writeText(els.testResponse.value).then(() => {
            const original = els.btnCopyResponse.textContent;
            els.btnCopyResponse.textContent = "Copied!";
            setTimeout(() => { els.btnCopyResponse.textContent = original; }, 1500);
        });
    });

    els.btnExportExcel.addEventListener("click", async () => {
        const raw = els.testResponse.value;
        if (!raw) return;

        let responseData;
        try {
            responseData = JSON.parse(raw);
        } catch (exc) {
            setError(els.testError, "Response is not valid JSON and cannot be exported to Excel.");
            return;
        }

        try {
            const res = await fetch("/api/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ response: responseData, filename: "rista_export" }),
            });

            if (!res.ok) {
                const data = await res.json();
                setError(els.testError, data.error || "Export failed.");
                return;
            }

            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "rista_export.xlsx";
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
        } catch (exc) {
            setError(els.testError, `Export failed: ${exc.message}`);
        }
    });

    els.btnExecute.addEventListener("click", async () => {
        clearError(els.composerError);
        els.composerResults.classList.add("hidden");
        els.composerResults.innerHTML = "";
        els.workflowSummary.classList.add("hidden");
        els.workflowSummary.innerHTML = "";

        const executionMode = els.runMode.value;
        const method = els.runMethod.value;

        els.btnExecute.disabled = true;
        els.executeProgress.classList.remove("hidden");

        try {
            if (executionMode === "custom_report") {
                await handleCustomReport();
            } else if (executionMode === "iterate_by_branch") {
                await handleIterateByBranch(method);
            } else {
                await handleSingleRequest(method);
            }
        } catch (exc) {
            els.executeProgress.classList.add("hidden");
            setError(els.composerError, `Network error: ${exc.message}`);
            els.btnExecute.disabled = false;
        }
    });

    async function handleSingleRequest(method) {
        const path = els.runPath.value.trim();
        if (!path) {
            setError(els.composerError, "Endpoint path is required.");
            els.btnExecute.disabled = false;
            return;
        }

        const requestDataRaw = els.commonRequest.value.trim();
        let requestData = {};
        if (requestDataRaw) {
            try {
                requestData = JSON.parse(requestDataRaw);
            } catch (exc) {
                setError(els.composerError, "Invalid JSON request data.");
                els.btnExecute.disabled = false;
                return;
            }
        }

        const body = {
            method: method,
            path: path,
            execution_mode: "single",
            request_data: requestData,
            api_key: els.jwtApiKey.value.trim(),
            secret_key: els.jwtSecretKey.value.trim(),
        };

        const res = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const data = await res.json();

        els.executeProgress.classList.add("hidden");

        if (!res.ok || !data.success) {
            setError(els.composerError, data.error || "Request failed.");
            els.btnExecute.disabled = false;
            return;
        }

        renderSingleResult(data);
        els.btnExecute.disabled = false;
    }

    async function handleIterateByBranch(method) {
        const path = els.runPath.value.trim();
        if (!path) {
            setError(els.composerError, "Endpoint path is required.");
            els.btnExecute.disabled = false;
            return;
        }

        const requestDataRaw = els.commonRequest.value.trim();
        let requestData = {};
        if (requestDataRaw) {
            try {
                requestData = JSON.parse(requestDataRaw);
            } catch (exc) {
                setError(els.composerError, "Invalid JSON request data.");
                els.btnExecute.disabled = false;
                return;
            }
        }

        els.executeProgress.textContent = "Starting iterate by branch...";

        const body = {
            method: method,
            path: path,
            execution_mode: "iterate_by_branch",
            request_data: requestData,
            api_key: els.jwtApiKey.value.trim(),
            secret_key: els.jwtSecretKey.value.trim(),
        };

        const res = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const startData = await res.json();

        if (!res.ok || !startData.success) {
            els.executeProgress.classList.add("hidden");
            setError(els.composerError, startData.error || "Failed to start iteration.");
            els.btnExecute.disabled = false;
            return;
        }

        const taskId = startData.task_id;
        let pollCount = 0;
        const maxPolls = 600;

        while (pollCount < maxPolls) {
            await new Promise(r => setTimeout(r, 1000));
            pollCount++;

            const statusRes = await fetch(`/api/workflow-status/${taskId}`);
            const statusData = await statusRes.json();

            if (!statusData.success) {
                els.executeProgress.classList.add("hidden");
                setError(els.composerError, statusData.error || "Status check failed.");
                els.btnExecute.disabled = false;
                return;
            }

            els.executeProgress.textContent = statusData.progress || "Processing...";

            if (statusData.status === "completed") {
                els.executeProgress.classList.add("hidden");
                renderIterateResults({
                    success: true,
                    mode: "iterate_by_branch",
                    path: path,
                    method: method,
                    branch_count: statusData.branch_count,
                    successful: statusData.successful,
                    failed: statusData.failed,
                    results: statusData.results,
                    consolidated: statusData.consolidated,
                });
                els.btnExecute.disabled = false;
                return;
            }

            if (statusData.status === "failed") {
                els.executeProgress.classList.add("hidden");
                setError(els.composerError, statusData.error || "Iteration failed.");
                els.btnExecute.disabled = false;
                return;
            }
        }

        els.executeProgress.classList.add("hidden");
        setError(els.composerError, "Iteration timed out. Please try again.");
        els.btnExecute.disabled = false;
    }

    async function handleCustomReport() {
        const startDate = els.reportStartDate.value.trim();
        const endDate = els.reportEndDate.value.trim();

        if (!startDate || !endDate) {
            setError(els.composerError, "Both start date and end date are required.");
            els.btnExecute.disabled = false;
            return;
        }

        const selectedApis = [];
        if (els.apiSalesSummary && els.apiSalesSummary.checked) {
            selectedApis.push("sales_summary");
        }
        if (els.apiDiscountTransactions && els.apiDiscountTransactions.checked) {
            selectedApis.push("discount_transactions");
        }

        if (selectedApis.length === 0) {
            setError(els.composerError, "Select at least one API for the custom report.");
            els.btnExecute.disabled = false;
            return;
        }

        const requestDataRaw = els.reportRequestData.value.trim();
        let requestData = {};
        if (requestDataRaw) {
            try {
                requestData = JSON.parse(requestDataRaw);
            } catch (exc) {
                setError(els.composerError, "Invalid JSON request data.");
                els.btnExecute.disabled = false;
                return;
            }
        }

        els.executeProgress.textContent = "Starting custom report...";

        const body = {
            start_date: startDate,
            end_date: endDate,
            apis: selectedApis,
            request_data: requestData,
            api_key: els.jwtApiKey.value.trim(),
            secret_key: els.jwtSecretKey.value.trim(),
        };

        const res = await fetch("/api/custom-report", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        const startData = await res.json();

        if (!res.ok || !startData.success) {
            els.executeProgress.classList.add("hidden");
            setError(els.composerError, startData.error || "Failed to start custom report.");
            els.btnExecute.disabled = false;
            return;
        }

        const taskId = startData.task_id;
        let pollCount = 0;
        const maxPolls = 600;

        while (pollCount < maxPolls) {
            await new Promise(r => setTimeout(r, 1000));
            pollCount++;

            const statusRes = await fetch(`/api/custom-report-status/${taskId}`);
            const statusData = await statusRes.json();

            if (!statusData.success) {
                els.executeProgress.classList.add("hidden");
                setError(els.composerError, statusData.error || "Status check failed.");
                els.btnExecute.disabled = false;
                return;
            }

            els.executeProgress.textContent = statusData.progress || "Processing...";

            if (statusData.status === "completed") {
                els.executeProgress.classList.add("hidden");
                renderCustomReport(statusData);
                els.btnExecute.disabled = false;
                return;
            }

            if (statusData.status === "failed") {
                els.executeProgress.classList.add("hidden");
                setError(els.composerError, statusData.error || "Custom report failed.");
                els.btnExecute.disabled = false;
                return;
            }
        }

        els.executeProgress.classList.add("hidden");
        setError(els.composerError, "Custom report timed out. Please try again.");
        els.btnExecute.disabled = false;
    }

    function renderSingleResult(data) {
        const statusClass = data.status_code >= 400 ? "error" : "success";
        const statusText = `HTTP ${data.status_code}`;
        const timeText = data.response_time_ms ? `${data.response_time_ms}ms` : "";

        let html = '<div class="results-header">Single Request</div>';
        html += `<div class="result-card">
            <div class="result-header">
                <div>
                    <div class="result-title">${escapeHtml(data.method)} ${escapeHtml(data.path)}</div>
                    <div class="result-meta">Single Request</div>
                </div>
                <div class="result-badges">
                    <span class="status ${statusClass}">${statusText}</span>
                    <span class="time-badge">${timeText}</span>
                </div>
            </div>`;

        const responseStr = typeof data.response === "string"
            ? data.response
            : JSON.stringify(data.response, null, 2);
        const escapedResponse = escapeHtml(responseStr);
        html += `<div class="result-body"><pre>${escapedResponse}</pre></div>`;
        html += `<div class="button-row"><button class="btn btn-secondary btn-copy-result" data-response="${escapeAttr(escapedResponse)}">Copy Response</button><button class="btn btn-secondary btn-export-single" data-response='${escapeAttr(JSON.stringify(data.response))}'>Export Excel</button></div>`;
        html += `</div>`;

        els.composerResults.innerHTML = html;
        els.composerResults.classList.remove("hidden");

        els.composerResults.querySelectorAll(".btn-copy-result").forEach(btn => {
            btn.addEventListener("click", () => {
                const response = btn.getAttribute("data-response");
                navigator.clipboard.writeText(response).then(() => {
                    const original = btn.textContent;
                    btn.textContent = "Copied!";
                    setTimeout(() => { btn.textContent = original; }, 1500);
                });
            });
        });

        els.composerResults.querySelectorAll(".btn-export-single").forEach(btn => {
            btn.addEventListener("click", async () => {
                try {
                    const responseData = JSON.parse(btn.getAttribute("data-response"));
                    const res = await fetch("/api/export", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ response: responseData, filename: "rista_export" }),
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        setError(els.composerError, err.error || "Export failed.");
                        return;
                    }
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "rista_export.xlsx";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } catch (exc) {
                    setError(els.composerError, `Export failed: ${exc.message}`);
                }
            });
        });
    }

    let viewAllConsolidated = false;

    function renderIterateResults(data) {
        viewAllConsolidated = false;
        const results = data.results || [];
        const consolidated = data.consolidated || {};
        const total = data.branch_count || results.length;
        const successful = data.successful || results.filter(r => r.success).length;
        const failed = data.failed || results.filter(r => !r.success).length;

        let summaryHtml = `
            <div class="workflow-summary-header">${escapeHtml(data.method)} ${escapeHtml(data.path)}</div>
            <div class="workflow-summary-stats">
                <span class="stat"><strong>${total}</strong> Total Branches</span>
                <span class="stat success"><strong>${successful}</strong> Successful</span>
                <span class="stat error"><strong>${failed}</strong> Failed</span>
            </div>
        `;
        els.workflowSummary.innerHTML = summaryHtml;
        els.workflowSummary.classList.remove("hidden");

        const consolidatedRows = consolidated.consolidated_rows || [];
        const branchSummary = consolidated.branch_summary || [];
        const overallTotals = consolidated.overall_totals || {};
        const failedBranches = consolidated.failed_branches || [];
        const numericFields = consolidated.numeric_fields || [];

        let html = '<div class="view-tabs">';
        html += `<button class="view-tab active" data-view="consolidated">Consolidated Report</button>`;
        html += `<button class="view-tab" data-view="branches">Branch Results</button>`;
        html += `<button class="view-tab" data-view="raw">Raw Responses</button>`;
        html += `</div>`;

        html += '<div class="view-panel active" id="view-consolidated">';
        html += `<div class="results-header">Consolidated Report <span class="consolidated-count">${consolidatedRows.length} records</span></div>`;

        if (overallTotals && Object.keys(overallTotals).length > 0) {
            html += '<div class="consolidated-totals">';
            html += '<div class="results-header">Overall Summary</div>';
            html += '<div class="totals-grid">';
            for (const [key, value] of Object.entries(overallTotals)) {
                const displayValue = Number.isInteger(value) ? value : value.toFixed(2);
                html += `<div class="total-item"><span class="total-label">${escapeHtml(key)}</span><span class="total-value">${displayValue}</span></div>`;
            }
            html += '</div></div>';
        }

        if (branchSummary.length > 0) {
            html += '<div class="results-header">Branch Summary</div>';
            html += '<div class="table-wrapper"><table class="data-table"><thead><tr>';
            html += '<th>Branch Code</th><th>Branch Name</th><th>Records</th>';
            for (const field of numericFields) {
                html += `<th>${escapeHtml(field)}</th>`;
            }
            html += '</tr></thead><tbody>';
            for (const b of branchSummary) {
                html += `<tr><td>${escapeHtml(b.branchCode)}</td><td>${escapeHtml(b.branchName)}</td><td>${b.recordCount}</td>`;
                for (const field of numericFields) {
                    const val = b.totals[field];
                    const displayVal = val !== undefined ? (Number.isInteger(val) ? val : val.toFixed(2)) : "-";
                    html += `<td>${displayVal}</td>`;
                }
                html += '</tr>';
            }
            if (numericFields.length > 0) {
                html += '<tr class="total-row"><td><strong>TOTAL</strong></td><td><strong>ALL BRANCHES</strong></td><td><strong>' + consolidatedRows.length + '</strong></td>';
                for (const field of numericFields) {
                    const val = overallTotals[field];
                    const displayVal = val !== undefined ? (Number.isInteger(val) ? val : val.toFixed(2)) : "-";
                    html += `<td><strong>${displayVal}</strong></td>`;
                }
                html += '</tr>';
            }
            html += '</tbody></table></div>';
        }

        if (consolidatedRows.length > 0) {
            const allKeys = new Set();
            for (const row of consolidatedRows) {
                for (const key of Object.keys(row)) {
                    allKeys.add(key);
                }
            }
            const columns = Array.from(allKeys);
            const displayRows = viewAllConsolidated ? consolidatedRows : consolidatedRows.slice(0, 5);

            html += '<div class="results-header">Detailed Consolidated Report</div>';
            html += '<div class="table-wrapper"><table class="data-table"><thead><tr>';
            for (const col of columns) {
                html += `<th>${escapeHtml(col)}</th>`;
            }
            html += '</tr></thead><tbody>';
            for (const row of displayRows) {
                html += '<tr>';
                for (const col of columns) {
                    const val = row[col];
                    html += `<td>${val !== undefined && val !== null ? escapeHtml(String(val)) : ""}</td>`;
                }
                html += '</tr>';
            }
            html += '</tbody></table></div>';

            html += '<div class="button-row consolidated-actions">';
            if (!viewAllConsolidated && consolidatedRows.length > 5) {
                html += `<button class="btn btn-secondary btn-view-all" data-rows='${escapeAttr(JSON.stringify(consolidatedRows))}' data-cols='${escapeAttr(JSON.stringify(columns))}'>View All (${consolidatedRows.length})</button>`;
            }
            html += `<button class="btn btn-secondary btn-download-csv" data-rows='${escapeAttr(JSON.stringify(consolidatedRows))}' data-cols='${escapeAttr(JSON.stringify(columns))}'>Download CSV</button>`;
            html += '</div>';
        }

        if (failedBranches.length > 0) {
            html += '<div class="results-header">Failed Branches</div>';
            html += '<div class="table-wrapper"><table class="data-table"><thead><tr><th>Branch Code</th><th>Branch Name</th><th>Status</th><th>Error</th></tr></thead><tbody>';
            for (const f of failedBranches) {
                html += `<tr><td>${escapeHtml(f.branchCode)}</td><td>${escapeHtml(f.branchName)}</td><td>${f.status_code || "N/A"}</td><td>${escapeHtml(f.error || "")}</td></tr>`;
            }
            html += '</tbody></table></div>';
        }

        html += '</div>';

        html += '<div class="view-panel" id="view-branches">';
        html += '<div class="results-header">Branch Results</div>';
        for (const result of results) {
            const statusClass = result.success && result.status_code && result.status_code < 400 ? "success" : "error";
            const statusText = result.success
                ? `HTTP ${result.status_code}`
                : `Error ${result.status_code || "N/A"}`;
            const timeText = result.execution_time_ms ? `${result.execution_time_ms}ms` : "";
            const title = `${escapeHtml(result.branchCode)} — ${escapeHtml(result.branchName || result.branchCode)}`;
            const cardClass = result.success ? "workflow-result-card result-success" : "workflow-result-card result-error";

            html += `<div class="result-card ${cardClass}">
                <div class="result-header">
                    <div>
                        <div class="result-title">${title}</div>
                        <div class="result-meta">${escapeHtml(data.method)} ${escapeHtml(data.path)}</div>
                    </div>
                    <div class="result-badges">
                        <span class="status ${statusClass}">${statusText}</span>
                        <span class="time-badge">${timeText}</span>
                    </div>
                </div>`;

            if (!result.success) {
                html += `<div class="result-error">${escapeHtml(result.error || "Unknown error")}</div>`;
            } else {
                const responseStr = typeof result.data === "string"
                    ? result.data
                    : JSON.stringify(result.data, null, 2);
                const escapedResponse = escapeHtml(responseStr);
                html += `<div class="result-body"><pre>${escapedResponse}</pre></div>`;
                html += `<div class="button-row"><button class="btn btn-secondary btn-copy-result" data-response="${escapeAttr(escapedResponse)}">Copy Response</button></div>`;
            }

            html += `</div>`;
        }
        html += '</div>';

        html += '<div class="view-panel" id="view-raw">';
        html += '<div class="results-header">Raw Responses</div>';
        const rawPayload = {
            consolidated: consolidated,
            results: results.map(r => ({
                branchCode: r.branchCode,
                branchName: r.branchName,
                success: r.success,
                status_code: r.status_code,
                execution_time_ms: r.execution_time_ms,
                data: r.data,
                error: r.error,
                endpoint: r.endpoint,
                request_params: r.request_params,
            })),
        };
        const rawStr = JSON.stringify(rawPayload, null, 2);
        html += `<div class="result-body"><pre>${escapeHtml(rawStr)}</pre></div>`;
        html += `<div class="button-row"><button class="btn btn-secondary btn-copy-result" data-response="${escapeAttr(escapeHtml(rawStr))}">Copy Raw JSON</button></div>`;
        html += '</div>';

        els.composerResults.innerHTML = html;
        els.composerResults.classList.remove("hidden");

        els.composerResults.querySelectorAll(".view-tab").forEach(tab => {
            tab.addEventListener("click", () => {
                els.composerResults.querySelectorAll(".view-tab").forEach(t => t.classList.remove("active"));
                els.composerResults.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
                tab.classList.add("active");
                const viewId = "view-" + tab.getAttribute("data-view");
                const panel = document.getElementById(viewId);
                if (panel) panel.classList.add("active");
            });
        });

        els.composerResults.querySelectorAll(".btn-copy-result").forEach(btn => {
            btn.addEventListener("click", () => {
                const response = btn.getAttribute("data-response");
                navigator.clipboard.writeText(response).then(() => {
                    const original = btn.textContent;
                    btn.textContent = "Copied!";
                    setTimeout(() => { btn.textContent = original; }, 1500);
                });
            });
        });

        els.composerResults.querySelectorAll(".btn-view-all").forEach(btn => {
            btn.addEventListener("click", () => {
                viewAllConsolidated = true;
                const allRows = JSON.parse(btn.getAttribute("data-rows"));
                const columns = JSON.parse(btn.getAttribute("data-cols"));
                const tableWrapper = btn.closest(".view-panel").querySelector(".table-wrapper:last-of-type");
                if (!tableWrapper) return;

                const table = tableWrapper.querySelector("table");
                if (!table) return;

                const tbody = table.querySelector("tbody");
                if (!tbody) return;

                let rowsHtml = "";
                for (const row of allRows) {
                    rowsHtml += '<tr>';
                    for (const col of columns) {
                        const val = row[col];
                        rowsHtml += `<td>${val !== undefined && val !== null ? escapeHtml(String(val)) : ""}</td>`;
                    }
                    rowsHtml += '</tr>';
                }
                tbody.innerHTML = rowsHtml;

                btn.remove();
            });
        });

        els.composerResults.querySelectorAll(".btn-download-csv").forEach(btn => {
            btn.addEventListener("click", () => {
                const allRows = JSON.parse(btn.getAttribute("data-rows"));
                const columns = JSON.parse(btn.getAttribute("data-cols"));
                if (!allRows.length) return;

                const csvRows = [columns.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")];
                for (const row of allRows) {
                    const values = columns.map(col => {
                        const val = row[col] !== undefined && row[col] !== null ? String(row[col]) : "";
                        return `"${val.replace(/"/g, '""')}"`;
                    });
                    csvRows.push(values.join(","));
                }
                const csvContent = csvRows.join("\n");
                const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "consolidated_report.csv";
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            });
        });

        renderIterateExportButton(consolidated);
    }

    function renderCustomReport(data) {
        const customReport = data.custom_report || {};
        const rows = customReport.rows || [];
        const columns = customReport.columns || [];
        const fieldSources = customReport.field_sources || {};
        const dateRange = customReport.date_range || {};
        const selectedApis = customReport.selected_apis || [];

        let summaryHtml = `
            <div class="workflow-summary-header">Custom Report</div>
            <div class="workflow-summary-stats">
                <span class="stat"><strong>${rows.length}</strong> Total Records</span>
                <span class="stat"><strong>${dateRange.start || ""}</strong> to <strong>${dateRange.end || ""}</strong></span>
            </div>
        `;
        els.workflowSummary.innerHTML = summaryHtml;
        els.workflowSummary.classList.remove("hidden");

        let html = '<div class="view-tabs">';
        html += `<button class="view-tab active" data-view="report">Custom Report</button>`;
        html += `<button class="view-tab" data-view="sources">Field Sources</button>`;
        html += `<button class="view-tab" data-view="raw">Raw Response</button>`;
        html += `</div>`;

        html += '<div class="view-panel active" id="view-report">';
        html += `<div class="results-header">Custom Report <span class="consolidated-count">${rows.length} records</span></div>`;

        if (columns.length > 0 && rows.length > 0) {
            const displayRows = rows.slice(0, 5);

            html += '<div class="table-wrapper"><table class="data-table"><thead><tr>';
            for (const col of columns) {
                html += `<th>${escapeHtml(col)}</th>`;
            }
            html += '</tr></thead><tbody>';
            for (const row of displayRows) {
                html += '<tr>';
                for (const col of columns) {
                    const val = row[col];
                    html += `<td>${val !== undefined && val !== null ? escapeHtml(String(val)) : ""}</td>`;
                }
                html += '</tr>';
            }
            html += '</tbody></table></div>';

            html += '<div class="button-row consolidated-actions">';
            if (rows.length > 5) {
                html += `<button class="btn btn-secondary btn-view-all-custom" data-rows='${escapeAttr(JSON.stringify(rows))}' data-cols='${escapeAttr(JSON.stringify(columns))}'>View All (${rows.length})</button>`;
            }
            html += `<button class="btn btn-secondary btn-download-csv-custom" data-rows='${escapeAttr(JSON.stringify(rows))}' data-cols='${escapeAttr(JSON.stringify(columns))}'>Download CSV</button>`;
            html += `<button class="btn btn-secondary btn-export-custom" data-report='${escapeAttr(JSON.stringify(customReport))}'>Export Excel</button>`;
            html += '</div>';
        } else {
            html += '<p class="hint">No records found for the selected criteria.</p>';
        }

        html += '</div>';

        html += '<div class="view-panel" id="view-sources">';
        html += '<div class="results-header">Field Sources</div>';
        if (Object.keys(fieldSources).length > 0) {
            html += '<div class="table-wrapper"><table class="data-table"><thead><tr><th>Field</th><th>Source</th></tr></thead><tbody>';
            for (const [field, source] of Object.entries(fieldSources)) {
                html += `<tr><td>${escapeHtml(field)}</td><td>${escapeHtml(source)}</td></tr>`;
            }
            html += '</tbody></table></div>';
        }
        html += '</div>';

        html += '<div class="view-panel" id="view-raw">';
        html += '<div class="results-header">Raw Response</div>';
        const rawStr = JSON.stringify(customReport, null, 2);
        html += `<div class="result-body"><pre>${escapeHtml(rawStr)}</pre></div>`;
        html += `<div class="button-row"><button class="btn btn-secondary btn-copy-result" data-response="${escapeAttr(escapeHtml(rawStr))}">Copy Raw JSON</button></div>`;
        html += '</div>';

        els.composerResults.innerHTML = html;
        els.composerResults.classList.remove("hidden");

        els.composerResults.querySelectorAll(".view-tab").forEach(tab => {
            tab.addEventListener("click", () => {
                els.composerResults.querySelectorAll(".view-tab").forEach(t => t.classList.remove("active"));
                els.composerResults.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
                tab.classList.add("active");
                const viewId = "view-" + tab.getAttribute("data-view");
                const panel = document.getElementById(viewId);
                if (panel) panel.classList.add("active");
            });
        });

        els.composerResults.querySelectorAll(".btn-copy-result").forEach(btn => {
            btn.addEventListener("click", () => {
                const response = btn.getAttribute("data-response");
                navigator.clipboard.writeText(response).then(() => {
                    const original = btn.textContent;
                    btn.textContent = "Copied!";
                    setTimeout(() => { btn.textContent = original; }, 1500);
                });
            });
        });

        els.composerResults.querySelectorAll(".btn-view-all-custom").forEach(btn => {
            btn.addEventListener("click", () => {
                const allRows = JSON.parse(btn.getAttribute("data-rows"));
                const cols = JSON.parse(btn.getAttribute("data-cols"));
                const tableWrapper = btn.closest(".view-panel").querySelector(".table-wrapper:last-of-type");
                if (!tableWrapper) return;
                const table = tableWrapper.querySelector("table");
                if (!table) return;
                const tbody = table.querySelector("tbody");
                if (!tbody) return;

                let rowsHtml = "";
                for (const row of allRows) {
                    rowsHtml += '<tr>';
                    for (const col of cols) {
                        const val = row[col];
                        rowsHtml += `<td>${val !== undefined && val !== null ? escapeHtml(String(val)) : ""}</td>`;
                    }
                    rowsHtml += '</tr>';
                }
                tbody.innerHTML = rowsHtml;
                btn.remove();
            });
        });

        els.composerResults.querySelectorAll(".btn-download-csv-custom").forEach(btn => {
            btn.addEventListener("click", () => {
                const allRows = JSON.parse(btn.getAttribute("data-rows"));
                const columns = JSON.parse(btn.getAttribute("data-cols"));
                if (!allRows.length) return;

                const csvRows = [columns.map(c => `"${String(c).replace(/"/g, '""')}"`).join(",")];
                for (const row of allRows) {
                    const values = columns.map(col => {
                        const val = row[col] !== undefined && row[col] !== null ? String(row[col]) : "";
                        return `"${val.replace(/"/g, '""')}"`;
                    });
                    csvRows.push(values.join(","));
                }
                const csvContent = csvRows.join("\n");
                const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "custom_report.csv";
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            });
        });

        els.composerResults.querySelectorAll(".btn-export-custom").forEach(btn => {
            btn.addEventListener("click", async () => {
                try {
                    const report = JSON.parse(btn.getAttribute("data-report"));
                    const res = await fetch("/api/export", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ response: { custom_report: report }, filename: "custom_report" }),
                    });
                    if (!res.ok) {
                        const err = await res.json();
                        setError(els.composerError, err.error || "Export failed.");
                        return;
                    }
                    const blob = await res.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "custom_report.xlsx";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } catch (exc) {
                    setError(els.composerError, `Export failed: ${exc.message}`);
                }
            });
        });

        renderCustomReportExportButton(customReport);
    }

    function renderCustomReportExportButton(customReport) {
        const existing = document.getElementById("btn-custom-export");
        if (existing) existing.remove();

        const btn = document.createElement("button");
        btn.id = "btn-custom-export";
        btn.className = "btn btn-secondary";
        btn.textContent = "Export Excel";
        btn.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/export", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ response: { custom_report: customReport }, filename: "custom_report" }),
                });
                if (!res.ok) {
                    const data = await res.json();
                    setError(els.composerError, data.error || "Export failed.");
                    return;
                }
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "custom_report.xlsx";
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } catch (exc) {
                setError(els.composerError, `Export failed: ${exc.message}`);
            }
        });

        const buttonRow = document.createElement("div");
        buttonRow.className = "button-row";
        buttonRow.style.marginTop = "1rem";
        buttonRow.appendChild(btn);
        els.workflowSummary.appendChild(buttonRow);
    }

    function renderIterateExportButton(consolidated) {
        const existing = document.getElementById("btn-iterate-export");
        if (existing) existing.remove();

        const btn = document.createElement("button");
        btn.id = "btn-iterate-export";
        btn.className = "btn btn-secondary";
        btn.textContent = "Export Consolidated Excel";
        btn.addEventListener("click", async () => {
            try {
                const payload = consolidated || {};
                const res = await fetch("/api/export", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ response: payload, filename: "consolidated_report" }),
                });

                if (!res.ok) {
                    const data = await res.json();
                    setError(els.composerError, data.error || "Export failed.");
                    return;
                }

                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "consolidated_report.xlsx";
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } catch (exc) {
                setError(els.composerError, `Export failed: ${exc.message}`);
            }
        });

        const buttonRow = document.createElement("div");
        buttonRow.className = "button-row";
        buttonRow.style.marginTop = "1rem";
        buttonRow.appendChild(btn);
        els.workflowSummary.appendChild(buttonRow);
    }

    loadConfig();
    loadCatalog();
});
