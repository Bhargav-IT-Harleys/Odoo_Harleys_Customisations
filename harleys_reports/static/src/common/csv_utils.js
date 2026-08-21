export function csvField(value) {
    const str = value === null || value === undefined ? "" : String(value);
    return '"' + str.replace(/"/g, '""') + '"';
}

export function safeCsvValue(value) {
    if (typeof value === "string" && /^[=+\-@]/.test(value)) {
        return "'" + value;
    }
    return value;
}

export function buildClientCsv(columns, rows) {
    const lines = [columns.map((column) => csvField(column.label)).join(",")];
    for (const row of rows) {
        lines.push(columns.map((column) => csvField(safeCsvValue(row[column.key]))).join(","));
    }
    return lines.join("\r\n");
}

export function downloadClientCsv(filename, content) {
    const blob = new Blob(["﻿" + content], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
