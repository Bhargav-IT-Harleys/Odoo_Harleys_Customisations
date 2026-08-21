import csv
import io
import json
import logging
import re

from odoo import fields, http
from odoo.http import content_disposition, request


_logger = logging.getLogger(__name__)


class HarleysReportsExport(http.Controller):
    @http.route(
        ["/harleys_reports/export/csv", "/harleys_reports/export/xlsx", "/harleys_reports/export/pdf"],
        type="http",
        auth="user",
        methods=["POST"],
        readonly=True,
    )
    def export_report(self, data, **kwargs):
        payload = json.loads(data)
        service = request.env["harleys.reports.service"]
        row_ids = payload.get("row_ids")
        if row_ids:
            row_ids = [int(rid) for rid in row_ids]
        model_name = payload.get("model_name")
        if model_name:
            provider = service._get_dynamic_provider(model_name)
            column_keys = payload.get("columns") or []
            rows = provider.export_rows(column_keys, payload.get("filters") or {}, payload.get("sort") or {}, row_ids=row_ids)
            columns = provider.columns_meta(column_keys)
        else:
            provider = service._get_provider(payload.get("report_key"))
            rows = provider.export_rows(payload.get("filters") or {}, payload.get("sort") or {}, row_ids=row_ids)
            columns = provider.columns
        extension = request.httprequest.path.rsplit("/", 1)[-1]
        meta_line = self._meta_line(request.env.user)
        if extension == "csv":
            body, content_type = self._csv(columns, rows), "text/csv;charset=utf-8"
        elif extension == "pdf":
            body, content_type = self._pdf(columns, rows, provider.title, meta_line), "application/pdf"
        else:
            body, content_type = (
                self._xlsx(columns, rows, provider.title, meta_line),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        _logger.info(
            "User %s exported %s rows from Harleys report %s as %s",
            request.env.user.id, len(rows), provider.key, extension,
        )
        filename = f"{(model_name or provider.key).replace('.', '_')}.{extension}"
        return request.make_response(body, headers=[
            ("Content-Type", content_type),
            ("Content-Disposition", content_disposition(filename)),
        ])

    @staticmethod
    def _meta_line(user):
        # Same letterhead line the on-screen report header shows, so an exported file carries
        # the same "who generated this, and when" audit trail once it leaves the app.
        employee = user.employee_id if "employee_id" in user._fields else False
        parts = [user.name]
        if employee and employee.barcode:
            parts.append(f"Emp ID {employee.barcode}")
        generated_at = fields.Datetime.context_timestamp(user, fields.Datetime.now())
        parts.append(f"Generated {generated_at.strftime('%Y-%m-%d %H:%M')}")
        return " | ".join(parts)

    @staticmethod
    def _safe_csv_value(value):
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + value
        return value

    def _csv(self, columns, rows):
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow([column["label"] for column in columns])
        for row in rows:
            writer.writerow([self._safe_csv_value(row.get(column["key"], "")) for column in columns])
        return output.getvalue().encode("utf-8-sig")

    @staticmethod
    def _xlsx(columns, rows, sheet_title="Export", meta_line=""):
        try:
            import xlsxwriter
        except ModuleNotFoundError as error:
            raise RuntimeError("XlsxWriter is required for XLSX exports.") from error
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        safe_title = re.sub(r'[:\\/?*\[\]]', " ", sheet_title).strip()[:31] or "Export"
        worksheet = workbook.add_worksheet(safe_title)
        # Only visible on the printed/PDF-exported page, not in the on-screen grid - Excel has
        # no concept of "pages" outside its print layout, so this is the only place page
        # numbers can live in an xlsx file.
        worksheet.set_header(f"&C&B&14HARLEYS REPORTS\n&12{sheet_title}\n&10{meta_line}")
        worksheet.set_footer("&CPage &P of &N")
        header = workbook.add_format({"bold": True, "bg_color": "#714B67", "font_color": "#FFFFFF"})
        for index, column in enumerate(columns):
            worksheet.write(0, index, column["label"], header)
            worksheet.set_column(index, index, 16 if column["type"] != "text" else 24)
        for row_index, row in enumerate(rows, start=1):
            for column_index, column in enumerate(columns):
                worksheet.write(row_index, column_index, row.get(column["key"], ""))
        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(rows), len(columns) - 1)
        workbook.close()
        return output.getvalue()

    @staticmethod
    def _pdf(columns, rows, title="Export", meta_line=""):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.units import mm
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfgen.canvas import Canvas
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ModuleNotFoundError as error:
            raise RuntimeError("ReportLab is required for PDF exports.") from error

        class _NumberedCanvas(Canvas):
            # Total page count isn't known until the whole document is laid out, so every
            # page is buffered first and only stamped with "Page X of N" on save().
            def __init__(self, *args, **kwargs):
                Canvas.__init__(self, *args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                total_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.setFont("Helvetica", 7)
                    self.setFillColor(colors.grey)
                    self.drawRightString(
                        self._pagesize[0] - 10 * mm, 8 * mm,
                        f"Page {self.getPageNumber()} of {total_pages}",
                    )
                    Canvas.showPage(self)
                Canvas.save(self)

        output = io.BytesIO()
        page_size = landscape(A4) if len(columns) > 5 else A4
        doc = SimpleDocTemplate(
            output, pagesize=page_size,
            leftMargin=10 * mm, rightMargin=10 * mm, topMargin=12 * mm, bottomMargin=16 * mm,
        )
        styles = getSampleStyleSheet()
        brand_style = ParagraphStyle(
            "HarleysBrand", parent=styles["Normal"], fontSize=8, leading=10,
            textColor=colors.HexColor("#714B67"), spaceAfter=2,
        )
        meta_style = ParagraphStyle(
            "HarleysMeta", parent=styles["Normal"], fontSize=8, leading=10,
            textColor=colors.grey, spaceAfter=8,
        )
        # Cell text is wrapped in Paragraphs (not plain strings) and colWidths is pinned to
        # doc.width - without both, reportlab sizes each column to fit its content and the
        # table overflows past the page edge instead of wrapping, clipping the outer columns.
        cell_style = ParagraphStyle("HarleysCell", parent=styles["Normal"], fontSize=6.5, leading=8)
        header_style = ParagraphStyle(
            "HarleysCellHeader", parent=cell_style, textColor=colors.white, fontName="Helvetica-Bold",
        )
        header_row = [Paragraph(column["label"], header_style) for column in columns]
        data = [header_row]
        for row in rows:
            data.append([Paragraph(str(row.get(column["key"], "") or ""), cell_style) for column in columns])

        weights = [2.6 if column["type"] == "text" else 1.3 for column in columns]
        total_weight = sum(weights)
        col_widths = [doc.width * weight / total_weight for weight in weights]

        table = Table(data, repeatRows=1, colWidths=col_widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#714B67")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F5F6")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements = [
            Paragraph("HARLEYS REPORTS", brand_style),
            Paragraph(title, styles["Heading2"]),
        ]
        elements.append(Paragraph(meta_line, meta_style) if meta_line else Spacer(1, 6))
        elements.append(table)
        doc.build(elements, canvasmaker=_NumberedCanvas)
        return output.getvalue()
