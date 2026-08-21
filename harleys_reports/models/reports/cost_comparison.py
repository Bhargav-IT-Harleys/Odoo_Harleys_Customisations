import csv
import io

from odoo.exceptions import ValidationError

# Header names recognised in the uploaded price sheet, case-insensitively. Everything else is
# ignored, so exports that still carry informational columns (category, unit, ...) parse fine.
_KNOWN_HEADERS = {
    "internal reference": "sku",
    "product name": "product_name",
    "price": "price",
    "new price": "price",
    "uploaded price": "price",
    "current price": "price",
}
_UNCHANGED_EPSILON = 0.01
_TOP_MOVERS_LIMIT = 5
_STATUSES = ("increased", "decreased", "unchanged", "no_baseline")


def _short_label(name):
    return name.rsplit("-", 1)[-1].strip() if "-" in name else name


def list_warehouses(env):
    # Cost is stored company-dependent on product.product - each warehouse's own company is
    # what actually determines "current cost", read live via with_company(), never uploaded.
    warehouses = env["stock.warehouse"].search([("code", "!=", False)], order="name")
    return [
        {
            "code": str(warehouse.id),
            "name": warehouse.name,
            "warehouse_code": warehouse.code,
            "company_id": warehouse.company_id.id,
            "region": _short_label(warehouse.company_id.name),
        }
        for warehouse in warehouses
    ]


def list_products_for_template(env):
    products = env["product.product"].search_read(
        [("default_code", "!=", False)],
        ["default_code", "name", "categ_id"],
        order="categ_id, name",
    )
    return [
        {
            "sku": product["default_code"],
            "name": product["name"],
            "category": product["categ_id"][1] if product["categ_id"] else "",
        }
        for product in products
    ]


def _parse_file(csv_content):
    if not isinstance(csv_content, str) or not csv_content.strip():
        raise ValidationError("The uploaded file is empty.")
    reader = csv.reader(io.StringIO(csv_content))
    try:
        header = next(reader)
    except StopIteration:
        raise ValidationError("The uploaded file has no header row.")
    columns = {}
    for index, raw_name in enumerate(header):
        key = _KNOWN_HEADERS.get((raw_name or "").strip().lower())
        if key and key not in columns:
            columns[key] = index
    if "sku" not in columns:
        raise ValidationError('The uploaded file is missing an "Internal Reference" column.')
    if "price" not in columns:
        raise ValidationError('The uploaded file is missing a "Price" column.')
    rows = [row for row in reader if any((cell or "").strip() for cell in row)]
    return columns, rows


def _cell(row, index):
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _find_product(env, sku):
    # Some SKUs in the real catalog are duplicated - a stale archived product left behind
    # alongside the current active one. Always prefer an active match; only fall back to
    # archived records (rather than reporting a false "unmatched") if nothing active matches,
    # since search() has no reason to prefer the live record when both are inactive-visible.
    product_model = env["product.product"]
    product = product_model.search([("default_code", "=", sku)], limit=1)
    if not product:
        product = product_model.search([("barcode", "=", sku)], limit=1)
    if not product:
        archived_model = product_model.with_context(active_test=False)
        product = archived_model.search([("default_code", "=", sku)], limit=1)
        if not product:
            product = archived_model.search([("barcode", "=", sku)], limit=1)
    return product


def _classify(uploaded_price, system_cost):
    if not system_cost:
        # No cost has ever been recorded for this product in this warehouse's company - there
        # is nothing to compare against, so this is neither an increase nor a decrease.
        return None, None, "no_baseline"
    variance_abs = round(uploaded_price - system_cost, 2)
    variance_pct = round((variance_abs / system_cost) * 100, 1)
    if abs(variance_abs) < _UNCHANGED_EPSILON:
        status = "unchanged"
    elif variance_abs > 0:
        status = "increased"
    else:
        status = "decreased"
    return variance_abs, variance_pct, status


def compute_comparison(env, csv_content, warehouse_ids):
    columns, rows = _parse_file(csv_content)
    try:
        wh_ids = [int(w) for w in (warehouse_ids or [])]
    except (TypeError, ValueError):
        raise ValidationError("Invalid warehouse selection.")
    if not wh_ids:
        raise ValidationError("Select at least one warehouse to compare.")
    warehouses = env["stock.warehouse"].browse(wh_ids).exists()
    if not warehouses:
        raise ValidationError("The selected warehouses could not be found.")

    lines = []
    unmatched_products = []
    for row in rows:
        sku = _cell(row, columns.get("sku"))
        price_raw = _cell(row, columns.get("price"))
        if not sku or not price_raw:
            continue
        try:
            uploaded_price = float(price_raw)
        except ValueError:
            continue
        product_name = _cell(row, columns.get("product_name")) or sku
        product = _find_product(env, sku)
        if not product:
            unmatched_products.append({"sku": sku, "product_name": product_name})
            continue
        # A product's cost only varies by company, not by individual warehouse - cache it per
        # company so selecting many warehouses in the same region doesn't re-read it each time.
        cost_by_company = {}
        for warehouse in warehouses:
            company_id = warehouse.company_id.id
            if company_id not in cost_by_company:
                cost_by_company[company_id] = product.with_company(company_id).standard_price
            system_cost = cost_by_company[company_id]
            variance_abs, variance_pct, status = _classify(uploaded_price, system_cost)
            lines.append({
                "product_name": product.display_name,
                "sku": sku,
                "warehouse_code": str(warehouse.id),
                "warehouse_name": warehouse.name,
                "system_cost": system_cost,
                "uploaded_price": uploaded_price,
                "variance_abs": variance_abs,
                "variance_pct": variance_pct,
                "status": status,
            })

    warehouse_codes = [str(w) for w in wh_ids]
    return {
        "warehouse_codes": warehouse_codes,
        "total_rows": len(rows),
        "unmatched_products": unmatched_products,
        "stats": _aggregate(lines),
        "per_warehouse": _aggregate_by_warehouse(lines, warehouse_codes),
        "top_movers": _top_movers(lines),
        "lines": lines,
    }


def _aggregate(lines):
    counts = {status: 0 for status in _STATUSES}
    variance_sum = 0.0
    variance_count = 0
    for line in lines:
        counts[line["status"]] += 1
        if line["variance_pct"] is not None:
            variance_sum += line["variance_pct"]
            variance_count += 1
    return {
        "total_compared": len(lines),
        "increased": counts["increased"],
        "decreased": counts["decreased"],
        "unchanged": counts["unchanged"],
        "no_baseline": counts["no_baseline"],
        "avg_variance_pct": round(variance_sum / variance_count, 1) if variance_count else 0,
    }


def _aggregate_by_warehouse(lines, codes):
    result = []
    for code in codes:
        warehouse_lines = [line for line in lines if line["warehouse_code"] == code]
        if not warehouse_lines:
            continue
        stats = _aggregate(warehouse_lines)
        result.append({
            "warehouse_code": code,
            "warehouse_name": warehouse_lines[0]["warehouse_name"],
            "total": stats["total_compared"],
            "increased": stats["increased"],
            "decreased": stats["decreased"],
            "unchanged": stats["unchanged"],
            "no_baseline": stats["no_baseline"],
            "avg_variance_pct": stats["avg_variance_pct"],
        })
    return result


def _top_movers(lines):
    priced = [line for line in lines if line["variance_pct"] is not None]
    increases = sorted(
        (line for line in priced if line["status"] == "increased"),
        key=lambda line: line["variance_pct"], reverse=True,
    )[:_TOP_MOVERS_LIMIT]
    decreases = sorted(
        (line for line in priced if line["status"] == "decreased"),
        key=lambda line: line["variance_pct"],
    )[:_TOP_MOVERS_LIMIT]
    return {"increases": increases, "decreases": decreases}
