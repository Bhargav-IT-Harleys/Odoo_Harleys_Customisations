import os
import io
import json
import uuid
import logging
import time
import threading
from datetime import datetime, timezone

import jwt
import pandas as pd
import requests
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RISTA_API_KEY = os.getenv("RISTA_API_KEY", "")
RISTA_SECRET_KEY = os.getenv("RISTA_SECRET_KEY", "")
RISTA_BASE_URL = os.getenv("RISTA_BASE_URL", "https://api.ristaapps.com/v1").rstrip("/")
RISTA_BRANCH_LIST_PATH = os.getenv("RISTA_BRANCH_LIST_PATH", "/branch/list")
RISTA_SALES_SUMMARY_PATH = os.getenv("RISTA_SALES_SUMMARY_PATH", "/analytics/sales/summary")
RISTA_DISCOUNT_TRANSACTIONS_PATH = os.getenv("RISTA_DISCOUNT_TRANSACTIONS_PATH", "/analytics/discount/transactions")
RISTA_REQUEST_DELAY = float(os.getenv("RISTA_REQUEST_DELAY", "0"))
RISTA_DEV_LOGGING = os.getenv("RISTA_DEV_LOGGING", "false").lower() in ("1", "true", "yes")
API_CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_catalog.json")

with open(API_CATALOG_PATH, "r", encoding="utf-8") as f:
    API_CATALOG = json.load(f)

API_DEFINITIONS = {api["id"]: api for api in API_CATALOG.get("apis", [])}

_workflow_tasks = {}
_workflow_lock = threading.Lock()


def _update_task(task, **kwargs):
    with _workflow_lock:
        task.update(kwargs)


def _log_request(method, path, params):
    if not RISTA_DEV_LOGGING:
        return
    try:
        from urllib.parse import urlencode
        query = urlencode(params) if params else ""
        url = f"{RISTA_BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"
        logger.info("[DEV] %s %s", method.upper(), url)
    except Exception:
        pass


def _flatten_value(value):
    if isinstance(value, (str, int, float, bool)):
        return value
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def _normalize_response(response_body):
    if isinstance(response_body, str):
        return []

    records = []

    if isinstance(response_body, dict):
        candidates = []
        for key, value in response_body.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                candidates.append((key, value))
            elif isinstance(value, dict):
                for inner_key, inner_value in value.items():
                    if isinstance(inner_value, list) and inner_value and isinstance(inner_value[0], dict):
                        candidates.append((f"{key}.{inner_key}", inner_value))

        if not candidates:
            for key, value in response_body.items():
                if isinstance(value, list) and value and not isinstance(value[0], dict):
                    candidates.append((key, [{"value": v} for v in value]))

        if candidates:
            preferred_order = ["data.items", "items", "data", "records", "results"]
            candidates.sort(key=lambda x: (
                0 if x[0] in preferred_order else 1,
                preferred_order.index(x[0]) if x[0] in preferred_order else 999,
                x[0],
            ))
            _, records = candidates[0]

    elif isinstance(response_body, list):
        if response_body and isinstance(response_body[0], dict):
            records = response_body
        elif response_body:
            records = [{"value": v} for v in response_body]

    normalized = []
    for record in records:
        flat = {}
        for key, value in record.items():
            flat[key] = _flatten_value(value)
        normalized.append(flat)

    return normalized


def _safe_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("₹", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def _consolidate_branch_results(results):
    successful_results = [r for r in results if r.get("success") and r.get("data") is not None]
    failed_results = [r for r in results if not r.get("success")]

    all_rows = []
    branch_summary = []
    overall_totals = {}
    numeric_fields = set()

    for result in successful_results:
        branch_code = result.get("branchCode", "")
        branch_name = result.get("branchName", branch_code)
        rows = _normalize_response(result.get("data"))

        branch_total = {}
        branch_count = 0

        for row in rows:
            row["branchCode"] = branch_code
            row["branchName"] = branch_name
            all_rows.append(row)
            branch_count += 1

            for key, value in row.items():
                if key in ("branchCode", "branchName"):
                    continue
                num = _safe_number(value)
                if num is not None:
                    numeric_fields.add(key)
                    overall_totals[key] = overall_totals.get(key, 0) + num
                    branch_total[key] = branch_total.get(key, 0) + num

        branch_summary.append({
            "branchCode": branch_code,
            "branchName": branch_name,
            "recordCount": branch_count,
            "totals": {k: v for k, v in branch_total.items()},
        })

    return {
        "consolidated_rows": all_rows,
        "branch_summary": branch_summary,
        "overall_totals": overall_totals,
        "numeric_fields": sorted(list(numeric_fields)),
        "failed_branches": [
            {
                "branchCode": r.get("branchCode", ""),
                "branchName": r.get("branchName", ""),
                "status_code": r.get("status_code"),
                "error": r.get("error", ""),
            }
            for r in failed_results
        ],
    }


def mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return value[:4] + "****"
    return value[:4] + "****" + value[-4:]


def generate_jwt(method: str = "GET", api_key: str = "", secret_key: str = "") -> str:
    api_key = api_key or RISTA_API_KEY
    secret_key = secret_key or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        raise ValueError("RISTA_API_KEY and RISTA_SECRET_KEY must be configured.")

    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": api_key,
        "iat": now,
    }

    if method.upper() in ("POST", "PUT", "DELETE"):
        payload["jti"] = str(uuid.uuid4())

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token


def get_auth_headers(method: str = "GET", api_key: str = "", secret_key: str = "") -> dict:
    api_key = api_key or RISTA_API_KEY
    secret_key = secret_key or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        raise ValueError("RISTA_API_KEY and RISTA_SECRET_KEY must be configured.")

    token = generate_jwt(method, api_key=api_key, secret_key=secret_key)
    headers = {
        "x-api-key": api_key,
        "x-api-token": token,
    }
    if method.upper() in ("POST", "PUT", "DELETE"):
        headers["Content-Type"] = "application/json"
    return headers


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def api_config():
    return jsonify({
        "configured": bool(RISTA_API_KEY and RISTA_SECRET_KEY),
        "api_key_configured": bool(RISTA_API_KEY),
        "api_key_masked": mask_value(RISTA_API_KEY),
        "secret_key_configured": bool(RISTA_SECRET_KEY),
        "base_url": RISTA_BASE_URL,
    })


@app.route("/api/catalog")
def api_catalog():
    return jsonify(API_CATALOG)


@app.route("/api/generate-token", methods=["POST"])
def api_generate_token():
    data = request.get_json(silent=True) or {}
    method = data.get("method", "GET")
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add RISTA_API_KEY and RISTA_SECRET_KEY to .env, or enter them in the UI.",
        }), 400

    try:
        token = generate_jwt(method=method, api_key=api_key, secret_key=secret_key)
        return jsonify({
            "success": True,
            "token": token,
            "expires": None,
        })
    except Exception as exc:
        logger.error("JWT generation failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Failed to generate JWT: {str(exc)}",
        }), 500


@app.route("/api/test", methods=["POST"])
def api_test():
    data = request.get_json(silent=True) or {}
    method = data.get("method", "GET").upper()
    path = data.get("path", "")
    query = (data.get("query") or "").strip()
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "status_code": None,
            "error": "Rista API credentials are not configured. Add RISTA_API_KEY and RISTA_SECRET_KEY to .env, or enter them in the UI.",
        }), 400

    if not path:
        return jsonify({
            "success": False,
            "status_code": None,
            "error": "Endpoint path is required (e.g. /branch/list).",
        }), 400

    if not path.startswith("/"):
        path = "/" + path

    url = f"{RISTA_BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"

    try:
        headers = get_auth_headers(method, api_key=api_key, secret_key=secret_key)
    except Exception as exc:
        logger.error("JWT generation failed: %s", exc)
        return jsonify({
            "success": False,
            "status_code": None,
            "error": f"Failed to generate JWT: {str(exc)}",
        }), 500

    start_time = time.time()
    response = None
    try:
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            timeout=30,
        )
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.info("%s %s?%s -> %s -> %sms", method, path, query, response.status_code, elapsed_ms)

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                body = response.json()
            except ValueError:
                body = response.text
        else:
            body = response.text

        return jsonify({
            "success": True,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "response": body,
            "headers": dict(response.headers),
        })

    except requests.exceptions.Timeout:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s?%s -> timeout -> %sms", method, path, query, elapsed_ms)
        return jsonify({
            "success": False,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": "Request timed out. The Rista API did not respond within 30 seconds.",
        }), 504

    except requests.exceptions.ConnectionError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s?%s -> connection error -> %sms", method, path, query, elapsed_ms)
        return jsonify({
            "success": False,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Connection error: {str(exc)}",
        }), 502

    except requests.exceptions.RequestException as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s?%s -> request error -> %sms", method, path, query, elapsed_ms)
        return jsonify({
            "success": False,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Request failed: {str(exc)}",
        }), 500

    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s?%s -> unexpected error -> %sms", method, path, query, elapsed_ms)
        return jsonify({
            "success": False,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Unexpected error: {str(exc)}",
        }), 500


@app.route("/api/combined-sales", methods=["POST"])
def api_combined_sales():
    data = request.get_json(silent=True) or {}
    period = data.get("period", "").strip()
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add credentials in the UI or .env.",
        }), 400

    if not period:
        return jsonify({
            "success": False,
            "error": "Period is required. Use YYYY-MM-DD or YYYY-MM format.",
        }), 400

    try:
        branch_headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
    except Exception as exc:
        logger.error("JWT generation failed for branch list: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Failed to generate JWT: {str(exc)}",
        }), 500

    branch_url = f"{RISTA_BASE_URL}{RISTA_BRANCH_LIST_PATH}"
    try:
        branch_resp = requests.get(branch_url, headers=branch_headers, timeout=30)
    except Exception as exc:
        logger.error("Failed to fetch branches from %s: %s", RISTA_BRANCH_LIST_PATH, exc)
        return jsonify({
            "success": False,
            "error": f"Failed to fetch branches from {RISTA_BRANCH_LIST_PATH}: {str(exc)}",
        }), 502

    if branch_resp.status_code != 200:
        logger.error("Branch list failed: %s -> %s", branch_resp.status_code, branch_resp.text)
        return jsonify({
            "success": False,
            "status_code": branch_resp.status_code,
            "error": f"Failed to fetch branches from {RISTA_BRANCH_LIST_PATH}: {branch_resp.text}",
        }), 400

    branches_data = branch_resp.json()
    branches = branches_data.get("branches", []) if isinstance(branches_data, dict) else []
    if not branches:
        branches = branches_data.get("data", {}).get("branches", []) if isinstance(branches_data, dict) else []
    if not branches and isinstance(branches_data, list):
        branches = branches_data

    if not branches:
        return jsonify({
            "success": False,
            "error": "No branches found in /branch/list response.",
        }), 400

    summary_url = f"{RISTA_BASE_URL}{RISTA_SALES_SUMMARY_PATH}"
    all_records = []
    errors = []

    for branch in branches:
        branch_code = branch.get("branch_code") or branch.get("code")
        branch_name = branch.get("name")

        if not branch_code:
            errors.append({
                "branch_name": branch_name,
                "branch_code": None,
                "error": "Branch code not found in branch object.",
            })
            continue

        try:
            headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
        except Exception as exc:
            errors.append({
                "branch_name": branch_name,
                "branch_code": branch_code,
                "error": f"JWT generation failed: {str(exc)}",
            })
            continue

        params = {
            "branch": branch_code,
            "period": period,
        }

        try:
            sales_resp = requests.get(summary_url, headers=headers, params=params, timeout=30)
        except Exception as exc:
            errors.append({
                "branch_name": branch_name,
                "branch_code": branch_code,
                "error": f"Request failed: {str(exc)}",
            })
            continue

        if sales_resp.status_code == 200:
            sales_json = None
            items = []

            content_type = sales_resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    sales_json = sales_resp.json()
                except ValueError:
                    sales_json = None

            if sales_json is not None:
                items = sales_json.get("data", {}).get("items", [])
                if not items and isinstance(sales_json.get("data"), list):
                    items = sales_json.get("data", [])

            for item in items:
                record = {
                    "branch_name": branch_name,
                    "branch_code": branch_code,
                    "item_name": item.get("item_name"),
                    "item_code": item.get("item_code"),
                    "quantity": item.get("quantity"),
                    "rate": item.get("rate"),
                    "net_amount": item.get("net_amount"),
                    "total_amount": item.get("total_amount"),
                }
                all_records.append(record)
        else:
            raw_text = sales_resp.text[:500]
            errors.append({
                "branch_name": branch_name,
                "branch_code": branch_code,
                "error": f"HTTP {sales_resp.status_code}: {raw_text}",
            })

    return jsonify({
        "success": True,
        "period": period,
        "branch_list_endpoint": RISTA_BRANCH_LIST_PATH,
        "sales_summary_endpoint": RISTA_SALES_SUMMARY_PATH,
        "branches_processed": len(branches),
        "total_records": len(all_records),
        "data": all_records,
        "errors": errors,
    })


def _generate_date_range(start_date, end_date):
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return []

    if start > end:
        return []

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current = current.replace(day=current.day + 1)
    return dates


def _extract_nested_value(obj, path):
    if obj is None:
        return None
    if not path:
        return obj

    parts = path.replace("[]", "").split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else None
            except (ValueError, TypeError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def _normalize_sales_summary(response_body, branch_code, branch_name, report_date):
    if isinstance(response_body, str):
        return []

    records = []
    channels = []
    payments = []
    item_qty = None
    taxes = None

    if isinstance(response_body, dict):
        channels = _extract_nested_value(response_body, "channelSummary") or []
        if not channels:
            channels = _extract_nested_value(response_body, "channel_summary") or []
        payments = _extract_nested_value(response_body, "payments") or []
        item_qty = _extract_nested_value(response_body, "itemTotalQty")
        if item_qty is None:
            item_qty = _extract_nested_value(response_body, "item_total_qty")
        taxes = _extract_nested_value(response_body, "taxTotal")
        if taxes is None:
            taxes = _extract_nested_value(response_body, "taxAmount")
        if taxes is None:
            taxes = _extract_nested_value(response_body, "itemTotaltaxAmount")

    if not channels and isinstance(response_body, dict):
        for key, value in response_body.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                if any(k in value[0] for k in ["directCharge", "indirectCharge", "name"]):
                    channels = value
                    break

    if not channels:
        channels = [{}]

    payment_modes = []
    if isinstance(payments, list):
        for p in payments:
            mode = p.get("mode") if isinstance(p, dict) else None
            if mode:
                payment_modes.append(mode)

    for channel in channels:
        if not isinstance(channel, dict):
            continue
        record = {
            "Date": report_date,
            "Time": "Not available",
            "Business Date": "Not available",
            "Invoice Date": None,
            "Invoice Number": None,
            "Invoice Type": None,
            "Tags": "Not available",
            "Sale Item Qty": item_qty,
            "Unit Rate": "Not available",
            "Taxes": taxes,
            "Tax Collected by Aggregator": "Not available",
            "Direct Charge": channel.get("directCharge"),
            "Indirect Charge": channel.get("indirectCharge"),
            "Channel": channel.get("name"),
            "Payment Modes": ", ".join(payment_modes) if payment_modes else None,
            "Branch Code": branch_code,
            "Branch Name": branch_name,
            "Source API": "/analytics/sales/summary",
        }
        records.append(record)

    return records


def _normalize_discount_transactions(response_body, branch_code, branch_name, report_date):
    if isinstance(response_body, str):
        return []

    transactions = []
    if isinstance(response_body, dict):
        transactions = response_body.get("data", [])
        if not transactions and isinstance(response_body.get("data"), list):
            transactions = response_body.get("data", [])
    elif isinstance(response_body, list):
        transactions = response_body

    records = []
    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        record = {
            "Date": report_date,
            "Time": "Not available",
            "Business Date": "Not available",
            "Invoice Date": tx.get("invoiceDate"),
            "Invoice Number": tx.get("invoiceNumber"),
            "Invoice Type": tx.get("invoiceType"),
            "Tags": "Not available",
            "Sale Item Qty": None,
            "Unit Rate": "Not available",
            "Taxes": None,
            "Tax Collected by Aggregator": "Not available",
            "Direct Charge": None,
            "Indirect Charge": None,
            "Channel": None,
            "Payment Modes": None,
            "Branch Code": branch_code,
            "Branch Name": branch_name,
            "Source API": "/analytics/discount/transactions",
        }
        records.append(record)
    return records


def _fetch_discount_transactions_with_pagination(api_key, secret_key, branch_code, report_date, method="GET"):
    headers = get_auth_headers(method, api_key=api_key, secret_key=secret_key)
    url = f"{RISTA_BASE_URL}{RISTA_DISCOUNT_TRANSACTIONS_PATH}"
    all_records = []
    last_key = None
    max_pages = 50
    page = 0

    while page < max_pages:
        page += 1
        params = {
            "branch": branch_code,
            "day": report_date,
        }
        if last_key:
            params["lastKey"] = last_key

        _log_request("GET", RISTA_DISCOUNT_TRANSACTIONS_PATH, params)

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except Exception as exc:
            logger.error("Discount transactions request failed: %s", exc)
            break

        if resp.status_code != 200:
            logger.error("Discount transactions failed: %s -> %s", resp.status_code, resp.text[:200])
            break

        try:
            body = resp.json()
        except (ValueError, TypeError):
            body = {}

        records = _normalize_discount_transactions(body, branch_code, None, report_date)
        all_records.extend(records)

        last_key = body.get("lastKey")
        if not last_key or not isinstance(last_key, str) or not last_key.strip():
            break

    return all_records


@app.route("/api/custom-report", methods=["POST"])
def api_custom_report():
    data = request.get_json(silent=True) or {}
    start_date = data.get("start_date", "").strip()
    end_date = data.get("end_date", "").strip()
    selected_apis = data.get("apis", [])
    request_data = data.get("request_data", {})
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add credentials in the UI or .env.",
        }), 400

    if not start_date or not end_date:
        return jsonify({
            "success": False,
            "error": "Both start_date and end_date are required (YYYY-MM-DD).",
        }), 400

    dates = _generate_date_range(start_date, end_date)
    if not dates:
        return jsonify({
            "success": False,
            "error": "Invalid date range. Use YYYY-MM-DD format.",
        }), 400

    include_sales = "sales_summary" in selected_apis
    include_discount = "discount_transactions" in selected_apis

    if not include_sales and not include_discount:
        return jsonify({
            "success": False,
            "error": "Select at least one data API (Sales Summary or Discount Transactions).",
        }), 400

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "mode": "custom_report",
        "status": "queued",
        "progress": "Starting...",
        "date_range": f"{start_date} to {end_date}",
        "total_dates": len(dates),
        "processed_dates": 0,
        "total_branches": 0,
        "processed_branches": 0,
        "successful_requests": 0,
        "failed_requests": 0,
        "custom_report": None,
        "field_sources": {},
        "error": None,
    }

    with _workflow_lock:
        _workflow_tasks[task_id] = task

    thread = threading.Thread(
        target=_run_custom_report,
        args=(task, dates, include_sales, include_discount, request_data, api_key, secret_key),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "mode": "custom_report",
        "task_id": task_id,
        "message": "Custom report started.",
    })


def _run_custom_report(task, dates, include_sales, include_discount, request_data, api_key, secret_key):
    try:
        common_params = dict(request_data) if request_data else {}
        if "branch" in common_params:
            del common_params["branch"]

        _update_task(task, progress="Fetching branch list...")

        try:
            headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
        except Exception as exc:
            logger.error("JWT generation failed for branch list: %s", exc)
            _update_task(task, status="failed", error=f"Failed to generate JWT: {str(exc)}")
            return

        branch_url = f"{RISTA_BASE_URL}{RISTA_BRANCH_LIST_PATH}"
        _log_request("GET", RISTA_BRANCH_LIST_PATH, {})
        try:
            branch_resp = requests.get(branch_url, headers=headers, timeout=30)
        except Exception as exc:
            logger.error("Failed to fetch branches from %s: %s", RISTA_BRANCH_LIST_PATH, exc)
            _update_task(task, status="failed", error=f"Failed to fetch branches from {RISTA_BRANCH_LIST_PATH}: {str(exc)}")
            return

        if branch_resp.status_code != 200:
            logger.error("Branch list failed: %s -> %s", branch_resp.status_code, branch_resp.text)
            _update_task(task, status="failed", error=f"Branch list failed ({branch_resp.status_code}): {branch_resp.text[:500]}")
            return

        branches_data = branch_resp.json()
        branches = []
        if isinstance(branches_data, dict):
            branches = branches_data.get("branches", [])
            if not branches:
                nested = branches_data.get("data")
                if isinstance(nested, dict):
                    branches = nested.get("branches", [])
        elif isinstance(branches_data, list):
            branches = branches_data

        if not branches:
            _update_task(task, status="failed", error="No branches found in branch list response.")
            return

        valid_branches = []
        seen_codes = set()
        for b in branches:
            code = b.get("branchCode") or b.get("code") or b.get("branch_code")
            name = b.get("branchName") or b.get("name")
            if code and code not in seen_codes:
                seen_codes.add(code)
                valid_branches.append({"branchCode": code, "branchName": name or code})

        if not valid_branches:
            _update_task(task, status="failed", error="No valid branch codes found in branch list response.")
            return

        total_combinations = len(valid_branches) * len(dates)
        _update_task(
            task,
            progress=f"Found {len(valid_branches)} branches and {len(dates)} dates. Processing {total_combinations} requests...",
            total_branches=len(valid_branches),
        )

        all_rows = []
        successful = 0
        failed = 0
        branch_records = {}

        for branch in valid_branches:
            branch_code = branch["branchCode"]
            branch_name = branch["branchName"]
            branch_records[branch_code] = {
                "branchName": branch_name,
                "sales_rows": [],
                "discount_rows": [],
            }

            for date_idx, report_date in enumerate(dates, 1):
                request_params = dict(common_params)
                request_params["branch"] = branch_code

                _update_task(
                    task,
                    progress=f"Processing {branch_code} - {report_date} ({task['processed_branches'] + 1}/{len(valid_branches)})",
                    processed_branches=task["processed_branches"] + 1,
                )

                if include_sales:
                    sales_params = dict(request_params)
                    sales_params["period"] = report_date
                    _log_request("GET", RISTA_SALES_SUMMARY_PATH, sales_params)
                    try:
                        sales_headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
                        sales_resp = requests.get(
                            f"{RISTA_BASE_URL}{RISTA_SALES_SUMMARY_PATH}",
                            headers=sales_headers,
                            params=sales_params,
                            timeout=30,
                        )

                        if sales_resp.status_code == 200:
                            sales_body = sales_resp.json()
                            sales_rows = _normalize_sales_summary(sales_body, branch_code, branch_name, report_date)
                            all_rows.extend(sales_rows)
                            branch_records[branch_code]["sales_rows"].extend(sales_rows)
                            successful += 1
                        else:
                            failed += 1
                            logger.error("Sales summary failed for %s %s: %s", branch_code, report_date, sales_resp.status_code)
                    except Exception as exc:
                        failed += 1
                        logger.error("Sales summary error for %s %s: %s", branch_code, report_date, exc)

                if include_discount:
                    try:
                        discount_rows = _fetch_discount_transactions_with_pagination(
                            api_key, secret_key, branch_code, report_date
                        )
                        all_rows.extend(discount_rows)
                        branch_records[branch_code]["discount_rows"].extend(discount_rows)
                        successful += 1
                    except Exception as exc:
                        failed += 1
                        logger.error("Discount transactions error for %s %s: %s", branch_code, report_date, exc)

                if RISTA_REQUEST_DELAY > 0:
                    time.sleep(RISTA_REQUEST_DELAY)

        field_sources = {
            "Date": "Request Period",
            "Time": "Not currently available",
            "Business Date": "Not currently available",
            "Invoice Date": "Discount Transactions" if include_discount else "Not available",
            "Invoice Number": "Discount Transactions" if include_discount else "Not available",
            "Invoice Type": "Discount Transactions" if include_discount else "Not available",
            "Tags": "Not currently available",
            "Sale Item Qty": "Sales Summary" if include_sales else "Not available",
            "Unit Rate": "Not currently available",
            "Taxes": "Sales Summary" if include_sales else "Not available",
            "Tax Collected by Aggregator": "Not currently available",
            "Direct Charge": "Sales Summary" if include_sales else "Not available",
            "Indirect Charge": "Sales Summary" if include_sales else "Not available",
            "Channel": "Sales Summary" if include_sales else "Not available",
            "Payment Modes": "Sales Summary" if include_sales else "Not available",
        }

        custom_report = {
            "columns": [
                "Date", "Time", "Business Date", "Invoice Date", "Invoice Number",
                "Invoice Type", "Tags", "Sale Item Qty", "Unit Rate", "Taxes",
                "Tax Collected by Aggregator", "Direct Charge", "Indirect Charge",
                "Channel", "Payment Modes", "Branch Code", "Branch Name", "Source API"
            ],
            "rows": all_rows,
            "field_sources": field_sources,
            "branch_records": branch_records,
            "date_range": {
                "start": start_date,
                "end": end_date,
                "dates": dates,
            },
            "selected_apis": selected_apis,
        }

        _update_task(
            task,
            status="completed",
            progress="Completed",
            successful=successful,
            failed=failed,
            custom_report=custom_report,
            field_sources=field_sources,
        )

    except Exception as exc:
        logger.error("Custom report failed unexpectedly: %s", exc)
        _update_task(task, status="failed", error=f"Unexpected error: {str(exc)}")


@app.route("/api/custom-report-status/<task_id>")
def api_custom_report_status(task_id):
    with _workflow_lock:
        task = _workflow_tasks.get(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": "Task not found.",
        }), 404

    return jsonify({
        "success": True,
        "status": task["status"],
        "progress": task["progress"],
        "date_range": task.get("date_range"),
        "total_dates": task.get("total_dates"),
        "processed_dates": task.get("processed_dates"),
        "total_branches": task.get("total_branches"),
        "processed_branches": task.get("processed_branches"),
        "successful_requests": task.get("successful_requests"),
        "failed_requests": task.get("failed_requests"),
        "custom_report": task.get("custom_report") if task["status"] == "completed" else None,
        "field_sources": task.get("field_sources"),
        "error": task["error"],
    })


@app.route("/api/export", methods=["POST"])
def api_export():
    data = request.get_json(silent=True) or {}
    response_data = data.get("response")
    filename = data.get("filename", "rista_export")

    if response_data is None:
        return jsonify({
            "success": False,
            "error": "No response data available to export.",
        }), 400

    try:
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            if isinstance(response_data, dict) and "custom_report" in response_data:
                custom_report = response_data["custom_report"]
                rows = custom_report.get("rows", [])
                columns = custom_report.get("columns", [])
                field_sources = custom_report.get("field_sources", {})

                if columns and rows:
                    df = pd.DataFrame(rows)
                    if set(columns).issubset(set(df.columns)):
                        df = df[columns]
                    df.to_excel(writer, index=False, sheet_name="Custom Report")

                if field_sources:
                    source_rows = [{"Field": k, "Source": v} for k, v in field_sources.items()]
                    df_sources = pd.json_normalize(source_rows)
                    df_sources.to_excel(writer, index=False, sheet_name="Field Sources")
            elif isinstance(response_data, dict) and "consolidated_rows" in response_data:
                consolidated = response_data
                rows = consolidated.get("consolidated_rows", [])
                branch_summary = consolidated.get("branch_summary", [])
                overall_totals = consolidated.get("overall_totals", {})
                failed_branches = consolidated.get("failed_branches", [])

                if rows:
                    df_rows = pd.json_normalize(rows)
                    df_rows.to_excel(writer, index=False, sheet_name="Consolidated Report")

                if branch_summary:
                    summary_rows = []
                    for b in branch_summary:
                        row = {
                            "branchCode": b.get("branchCode", ""),
                            "branchName": b.get("branchName", ""),
                            "recordCount": b.get("recordCount", 0),
                        }
                        for k, v in b.get("totals", {}).items():
                            row[k] = v
                        summary_rows.append(row)

                    if summary_rows:
                        df_summary = pd.json_normalize(summary_rows)
                        df_summary.to_excel(writer, index=False, sheet_name="Branch Summary")

                if overall_totals:
                    df_overall = pd.json_normalize([{
                        "metric": k,
                        "total": v,
                    } for k, v in overall_totals.items()])
                    df_overall.to_excel(writer, index=False, sheet_name="Overall Totals")

                if failed_branches:
                    df_failed = pd.json_normalize(failed_branches)
                    df_failed.to_excel(writer, index=False, sheet_name="Failed Branches")
            else:
                if isinstance(response_data, dict):
                    df = pd.json_normalize(response_data)
                elif isinstance(response_data, list):
                    df = pd.json_normalize(response_data)
                else:
                    df = pd.DataFrame([{"value": response_data}])

                df.to_excel(writer, index=False, sheet_name="Sheet1")

        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{filename}.xlsx",
        )
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        return jsonify({
            "success": False,
            "error": f"Failed to export data: {str(exc)}",
        }), 500


@app.route("/api/execute", methods=["POST"])
def api_execute():
    data = request.get_json(silent=True) or {}
    api_ids = data.get("apis", [])
    request_data = data.get("request_data", {})

    if not isinstance(api_ids, list) or not api_ids:
        return jsonify({
            "success": False,
            "error": "No APIs selected.",
        }), 400

    if request_data is None:
        request_data = {}

    if not isinstance(request_data, dict):
        return jsonify({
            "success": False,
            "error": "Invalid JSON request data.",
        }), 400

    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add credentials in the UI or .env.",
        }), 400

    results = []

    for api_id in api_ids:
        api_def = API_DEFINITIONS.get(api_id)
        if not api_def:
            results.append({
                "api_id": api_id,
                "success": False,
                "status_code": None,
                "error": f"Unknown API ID: {api_id}",
            })
            continue

        if not api_def.get("enabled", True):
            results.append({
                "api_id": api_id,
                "success": False,
                "status_code": None,
                "error": f"API is disabled: {api_id}",
            })
            continue

        method = api_def.get("method", "GET").upper()
        path = api_def.get("path", "")
        request_type = api_def.get("request_type", "query")

        if not path.startswith("/"):
            path = "/" + path

        url = f"{RISTA_BASE_URL}{path}"

        required_params = api_def.get("parameters", [])
        if required_params:
            missing = [p for p in required_params if p not in request_data or not request_data[p]]
            if missing:
                results.append({
                    "api_id": api_id,
                    "name": api_def.get("name"),
                    "method": method,
                    "path": path,
                    "request_type": request_type,
                    "success": False,
                    "status_code": None,
                    "response_time_ms": 0,
                    "error": f"Missing required parameter(s): {', '.join(missing)}",
                })
                continue

        try:
            headers = get_auth_headers(method, api_key=api_key, secret_key=secret_key)
        except Exception as exc:
            logger.error("JWT generation failed for %s: %s", api_id, exc)
            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": False,
                "status_code": None,
                "response_time_ms": 0,
                "error": f"Failed to generate JWT: {str(exc)}",
            })
            continue

        start_time = time.time()
        response = None
        try:
            if request_type == "query" and request_data:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=request_data,
                    timeout=30,
                )
            elif request_type == "body" and request_data:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=request_data,
                    timeout=30,
                )
            else:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=30,
                )

            elapsed_ms = round((time.time() - start_time) * 1000)
            logger.info("%s %s -> %s -> %sms", method, path, response.status_code, elapsed_ms)

            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                try:
                    body = response.json()
                except ValueError:
                    body = response.text
            else:
                body = response.text

            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": True,
                "status_code": response.status_code,
                "response_time_ms": elapsed_ms,
                "response": body,
            })

        except requests.exceptions.Timeout:
            elapsed_ms = round((time.time() - start_time) * 1000)
            logger.error("%s %s -> timeout -> %sms", method, path, elapsed_ms)
            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "error": "Request timed out after 30 seconds.",
            })

        except requests.exceptions.ConnectionError as exc:
            elapsed_ms = round((time.time() - start_time) * 1000)
            logger.error("%s %s -> connection error -> %sms", method, path, elapsed_ms)
            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "error": f"Connection error: {str(exc)}",
            })

        except requests.exceptions.RequestException as exc:
            elapsed_ms = round((time.time() - start_time) * 1000)
            logger.error("%s %s -> request error -> %sms", method, path, elapsed_ms)
            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "error": f"Request failed: {str(exc)}",
            })

        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000)
            logger.error("%s %s -> unexpected error -> %sms", method, path, elapsed_ms)
            results.append({
                "api_id": api_id,
                "name": api_def.get("name"),
                "method": method,
                "path": path,
                "request_type": request_type,
                "success": False,
                "status_code": None,
                "response_time_ms": elapsed_ms,
                "error": f"Unexpected error: {str(exc)}",
            })

    return jsonify({
        "success": True,
        "results": results,
    })


@app.route("/api/workflow", methods=["POST"])
def api_workflow():
    data = request.get_json(silent=True) or {}
    workflow_id = data.get("workflow_id", "")
    request_data = data.get("request_data", {})
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add credentials in the UI or .env.",
        }), 400

    if not workflow_id:
        return jsonify({
            "success": False,
            "error": "workflow_id is required.",
        }), 400

    workflow_def = API_DEFINITIONS.get(workflow_id)
    if not workflow_def:
        return jsonify({
            "success": False,
            "error": f"Unknown workflow: {workflow_id}",
        }), 400

    if not workflow_def.get("enabled", True):
        return jsonify({
            "success": False,
            "error": f"Workflow is disabled: {workflow_id}",
        }), 400

    workflow_type = workflow_def.get("workflow", {}).get("type")

    if workflow_type != "branch_iteration":
        return jsonify({
            "success": False,
            "error": f"Unsupported workflow type: {workflow_type}",
        }), 400

    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "workflow_id": workflow_id,
        "status": "queued",
        "progress": "Starting...",
        "branch_count": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "results": [],
        "error": None,
    }

    with _workflow_lock:
        _workflow_tasks[task_id] = task

    thread = threading.Thread(
        target=_run_branch_iteration_workflow,
        args=(task, workflow_def, request_data, api_key, secret_key),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Workflow started.",
    })


@app.route("/api/workflow-status/<task_id>")
def api_workflow_status(task_id):
    with _workflow_lock:
        task = _workflow_tasks.get(task_id)

    if not task:
        return jsonify({
            "success": False,
            "error": "Task not found.",
        }), 404

    return jsonify({
        "success": True,
        "status": task["status"],
        "progress": task["progress"],
        "branch_count": task["branch_count"],
        "processed": task["processed"],
        "successful": task["successful"],
        "failed": task["failed"],
        "results": task["results"] if task["status"] == "completed" else [],
        "consolidated": task.get("consolidated") if task["status"] == "completed" else None,
        "error": task["error"],
    })


def _run_branch_iteration_workflow(task, workflow_def, request_data, api_key, secret_key):
    try:
        branch_api_id = workflow_def["workflow"]["branch_api"]
        sales_api_id = workflow_def["workflow"]["sales_api"]

        branch_api_def = API_DEFINITIONS.get(branch_api_id)
        sales_api_def = API_DEFINITIONS.get(sales_api_id)

        if not branch_api_def or not sales_api_def:
            _update_task(task, status="failed", error="Workflow definition error.")
            return

        branch_path = branch_api_def["path"]
        sales_path = sales_api_def["path"]
        sales_method = sales_api_def.get("method", "GET").upper()
        sales_request_type = sales_api_def.get("request_type", "query")

        if request_data is None:
            request_data = {}
        if not isinstance(request_data, dict):
            _update_task(task, status="failed", error="Invalid request_data: must be a JSON object.")
            return

        common_params = dict(request_data)
        if "branch" in common_params:
            del common_params["branch"]

        _update_task(task, progress="Fetching branch list...")

        try:
            headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
        except Exception as exc:
            _update_task(task, status="failed", error=f"Failed to generate JWT: {str(exc)}")
            return

        branch_url = f"{RISTA_BASE_URL}{branch_path}"
        try:
            branch_resp = requests.get(branch_url, headers=headers, timeout=30)
        except Exception as exc:
            logger.error("Failed to fetch branches from %s: %s", branch_path, exc)
            _update_task(task, status="failed", error=f"Failed to fetch branches from {branch_path}: {str(exc)}")
            return

        if branch_resp.status_code != 200:
            logger.error("Branch list failed: %s -> %s", branch_resp.status_code, branch_resp.text)
            _update_task(task, status="failed", error=f"Branch list failed ({branch_resp.status_code}): {branch_resp.text[:500]}")
            return

        branches_data = branch_resp.json()
        branches = []
        if isinstance(branches_data, dict):
            branches = branches_data.get("branches", [])
            if not branches:
                nested = branches_data.get("data")
                if isinstance(nested, dict):
                    branches = nested.get("branches", [])
        elif isinstance(branches_data, list):
            branches = branches_data

        if not branches:
            _update_task(task, status="failed", error="No branches found in branch list response.")
            return

        valid_branches = []
        seen_codes = set()
        for b in branches:
            code = b.get("branchCode") or b.get("code") or b.get("branch_code")
            name = b.get("branchName") or b.get("name")
            if code and code not in seen_codes:
                seen_codes.add(code)
                valid_branches.append({"branchCode": code, "branchName": name or code})

        if not valid_branches:
            _update_task(task, status="failed", error="No valid branch codes found in branch list response.")
            return

        _update_task(task, progress=f"Found {len(valid_branches)} branches.", branch_count=len(valid_branches))

        results = []
        successful = 0
        failed = 0

        for i, branch in enumerate(valid_branches, 1):
            branch_code = branch["branchCode"]
            request_params = dict(common_params)
            request_params["branch"] = branch_code

            _update_task(task, progress=f"Fetching sales summary: {i} / {len(valid_branches)} — {branch_code}", processed=i)

            try:
                headers = get_auth_headers(sales_method, api_key=api_key, secret_key=secret_key)
            except Exception as exc:
                logger.error("JWT generation failed for branch %s: %s", branch_code, exc)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": 0,
                    "error": f"JWT generation failed: {str(exc)}",
                })
                failed += 1
                continue

            start_time = time.time()
            response = None
            try:
                if sales_request_type == "body" and sales_method in ("POST", "PUT", "PATCH"):
                    response = requests.request(
                        method=sales_method,
                        url=f"{RISTA_BASE_URL}{sales_path}",
                        headers=headers,
                        json=request_params,
                        timeout=30,
                    )
                else:
                    response = requests.get(
                        f"{RISTA_BASE_URL}{sales_path}",
                        headers=headers,
                        params=request_params,
                        timeout=30,
                    )

                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.info(
                    "%s %s?branch=%s -> %s -> %sms",
                    sales_method, sales_path, branch_code, response.status_code, elapsed_ms
                )

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        body = response.json()
                    except ValueError:
                        body = response.text
                else:
                    body = response.text

                if response.status_code == 200:
                    results.append({
                        "branchCode": branch_code,
                        "branchName": branch["branchName"],
                        "success": True,
                        "status_code": response.status_code,
                        "execution_time_ms": elapsed_ms,
                        "data": body,
                        "endpoint": sales_path,
                        "request_params": request_params,
                    })
                    successful += 1
                else:
                    results.append({
                        "branchCode": branch_code,
                        "branchName": branch["branchName"],
                        "success": False,
                        "status_code": response.status_code,
                        "execution_time_ms": elapsed_ms,
                        "error": response.text[:500],
                        "endpoint": sales_path,
                        "request_params": request_params,
                    })
                    failed += 1

            except requests.exceptions.Timeout:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> timeout -> %sms", sales_method, sales_path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": "Request timed out after 30 seconds.",
                    "endpoint": sales_path,
                    "request_params": request_params,
                })
                failed += 1

            except requests.exceptions.ConnectionError as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> connection error -> %sms", sales_method, sales_path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Connection error: {str(exc)}",
                    "endpoint": sales_path,
                    "request_params": request_params,
                })
                failed += 1

            except requests.exceptions.RequestException as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> request error -> %sms", sales_method, sales_path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Request failed: {str(exc)}",
                    "endpoint": sales_path,
                    "request_params": request_params,
                })
                failed += 1

            except Exception as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> unexpected error -> %sms", sales_method, sales_path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Unexpected error: {str(exc)}",
                    "endpoint": sales_path,
                    "request_params": request_params,
                })
                failed += 1

            if RISTA_REQUEST_DELAY > 0:
                time.sleep(RISTA_REQUEST_DELAY)

        _update_task(
            task,
            status="completed",
            progress="Completed",
            results=results,
            successful=successful,
            failed=failed,
            consolidated=_consolidate_branch_results(results),
        )

    except Exception as exc:
        logger.error("Workflow failed unexpectedly: %s", exc)
        _update_task(task, status="failed", error=f"Unexpected error: {str(exc)}")


@app.route("/api/run", methods=["POST"])
def api_run():
    data = request.get_json(silent=True) or {}
    method = data.get("method", "GET").upper()
    path = data.get("path", "").strip()
    execution_mode = data.get("execution_mode", "single")
    request_data = data.get("request_data", {})
    api_key = data.get("api_key") or RISTA_API_KEY
    secret_key = data.get("secret_key") or RISTA_SECRET_KEY

    if not api_key or not secret_key:
        return jsonify({
            "success": False,
            "error": "Rista API credentials are not configured. Add credentials in the UI or .env.",
        }), 400

    if not path:
        return jsonify({
            "success": False,
            "error": "Endpoint path is required.",
        }), 400

    if not path.startswith("/"):
        path = "/" + path

    if "http://" in path.lower() or "https://" in path.lower():
        return jsonify({
            "success": False,
            "error": "Only endpoint paths are allowed. Do not include protocol or host.",
        }), 400

    if request_data is None:
        request_data = {}
    if not isinstance(request_data, dict):
        return jsonify({
            "success": False,
            "error": "Invalid request_data: must be a JSON object.",
        }), 400

    if execution_mode == "iterate_by_branch":
        return _start_iterate_by_branch(method, path, request_data, api_key, secret_key)

    return _execute_single_request(method, path, request_data, api_key, secret_key)


def _execute_single_request(method, path, request_data, api_key, secret_key):
    url = f"{RISTA_BASE_URL}{path}"
    start_time = time.time()
    response = None

    try:
        headers = get_auth_headers(method, api_key=api_key, secret_key=secret_key)
    except Exception as exc:
        logger.error("JWT generation failed for %s: %s", path, exc)
        return jsonify({
            "success": False,
            "mode": "single",
            "method": method,
            "path": path,
            "error": f"Failed to generate JWT: {str(exc)}",
        }), 500

    try:
        if request_data:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=request_data if method == "GET" else None,
                json=request_data if method != "GET" else None,
                timeout=30,
            )
        else:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=30,
            )

        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.info("%s %s -> %s -> %sms", method, path, response.status_code, elapsed_ms)

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                body = response.json()
            except ValueError:
                body = response.text
        else:
            body = response.text

        return jsonify({
            "success": True,
            "mode": "single",
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "response": body,
            "headers": dict(response.headers),
        })

    except requests.exceptions.Timeout:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s -> timeout -> %sms", method, path, elapsed_ms)
        return jsonify({
            "success": False,
            "mode": "single",
            "method": method,
            "path": path,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": "Request timed out after 30 seconds.",
        }), 504

    except requests.exceptions.ConnectionError as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s -> connection error -> %sms", method, path, elapsed_ms)
        return jsonify({
            "success": False,
            "mode": "single",
            "method": method,
            "path": path,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Connection error: {str(exc)}",
        }), 502

    except requests.exceptions.RequestException as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s -> request error -> %sms", method, path, elapsed_ms)
        return jsonify({
            "success": False,
            "mode": "single",
            "method": method,
            "path": path,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Request failed: {str(exc)}",
        }), 500

    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000)
        logger.error("%s %s -> unexpected error -> %sms", method, path, elapsed_ms)
        return jsonify({
            "success": False,
            "mode": "single",
            "method": method,
            "path": path,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "error": f"Unexpected error: {str(exc)}",
        }), 500


def _start_iterate_by_branch(method, path, request_data, api_key, secret_key):
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "mode": "iterate_by_branch",
        "method": method,
        "path": path,
        "status": "queued",
        "progress": "Starting...",
        "branch_count": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "results": [],
        "error": None,
    }

    with _workflow_lock:
        _workflow_tasks[task_id] = task

    thread = threading.Thread(
        target=_run_iterate_by_branch,
        args=(task, method, path, request_data, api_key, secret_key),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "mode": "iterate_by_branch",
        "task_id": task_id,
        "message": "Iterate by branch started.",
    })


def _run_iterate_by_branch(task, method, path, request_data, api_key, secret_key):
    try:
        if request_data is None:
            request_data = {}
        if not isinstance(request_data, dict):
            _update_task(task, status="failed", error="Invalid request_data: must be a JSON object.")
            return

        common_params = dict(request_data)
        if "branch" in common_params:
            del common_params["branch"]

        _update_task(task, progress="Fetching branch list...")

        try:
            headers = get_auth_headers("GET", api_key=api_key, secret_key=secret_key)
        except Exception as exc:
            logger.error("JWT generation failed for branch list: %s", exc)
            _update_task(task, status="failed", error=f"Failed to generate JWT: {str(exc)}")
            return

        branch_url = f"{RISTA_BASE_URL}{RISTA_BRANCH_LIST_PATH}"
        try:
            branch_resp = requests.get(branch_url, headers=headers, timeout=30)
        except Exception as exc:
            logger.error("Failed to fetch branches from %s: %s", RISTA_BRANCH_LIST_PATH, exc)
            _update_task(task, status="failed", error=f"Failed to fetch branches from {RISTA_BRANCH_LIST_PATH}: {str(exc)}")
            return

        if branch_resp.status_code != 200:
            logger.error("Branch list failed: %s -> %s", branch_resp.status_code, branch_resp.text)
            _update_task(task, status="failed", error=f"Branch list failed ({branch_resp.status_code}): {branch_resp.text[:500]}")
            return

        branches_data = branch_resp.json()
        branches = []
        if isinstance(branches_data, dict):
            branches = branches_data.get("branches", [])
            if not branches:
                nested = branches_data.get("data")
                if isinstance(nested, dict):
                    branches = nested.get("branches", [])
        elif isinstance(branches_data, list):
            branches = branches_data

        if not branches:
            _update_task(task, status="failed", error="No branches found in branch list response.")
            return

        valid_branches = []
        seen_codes = set()
        for b in branches:
            code = b.get("branchCode") or b.get("code") or b.get("branch_code")
            name = b.get("branchName") or b.get("name")
            if code and code not in seen_codes:
                seen_codes.add(code)
                valid_branches.append({"branchCode": code, "branchName": name or code})

        if not valid_branches:
            _update_task(task, status="failed", error="No valid branch codes found in branch list response.")
            return

        _update_task(task, progress=f"Found {len(valid_branches)} branches.", branch_count=len(valid_branches))

        results = []
        successful = 0
        failed = 0

        for i, branch in enumerate(valid_branches, 1):
            branch_code = branch["branchCode"]
            request_params = dict(common_params)
            request_params["branch"] = branch_code

            _update_task(task, progress=f"Fetching: {i} / {len(valid_branches)} — {branch_code}", processed=i)

            try:
                headers = get_auth_headers(method, api_key=api_key, secret_key=secret_key)
            except Exception as exc:
                logger.error("JWT generation failed for branch %s: %s", branch_code, exc)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": 0,
                    "error": f"JWT generation failed: {str(exc)}",
                    "endpoint": path,
                    "request_params": request_params,
                })
                failed += 1
                continue

            start_time = time.time()
            response = None
            try:
                if request_params:
                    response = requests.request(
                        method=method,
                        url=f"{RISTA_BASE_URL}{path}",
                        headers=headers,
                        params=request_params if method == "GET" else None,
                        json=request_params if method != "GET" else None,
                        timeout=30,
                    )
                else:
                    response = requests.request(
                        method=method,
                        url=f"{RISTA_BASE_URL}{path}",
                        headers=headers,
                        timeout=30,
                    )

                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.info(
                    "%s %s?branch=%s -> %s -> %sms",
                    method, path, branch_code, response.status_code, elapsed_ms
                )

                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        body = response.json()
                    except ValueError:
                        body = response.text
                else:
                    body = response.text

                if response.status_code == 200:
                    results.append({
                        "branchCode": branch_code,
                        "branchName": branch["branchName"],
                        "success": True,
                        "status_code": response.status_code,
                        "execution_time_ms": elapsed_ms,
                        "data": body,
                        "endpoint": path,
                        "request_params": request_params,
                    })
                    successful += 1
                else:
                    results.append({
                        "branchCode": branch_code,
                        "branchName": branch["branchName"],
                        "success": False,
                        "status_code": response.status_code,
                        "execution_time_ms": elapsed_ms,
                        "error": response.text[:500],
                        "endpoint": path,
                        "request_params": request_params,
                    })
                    failed += 1

            except requests.exceptions.Timeout:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> timeout -> %sms", method, path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": "Request timed out after 30 seconds.",
                    "endpoint": path,
                    "request_params": request_params,
                })
                failed += 1

            except requests.exceptions.ConnectionError as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> connection error -> %sms", method, path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Connection error: {str(exc)}",
                    "endpoint": path,
                    "request_params": request_params,
                })
                failed += 1

            except requests.exceptions.RequestException as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> request error -> %sms", method, path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Request failed: {str(exc)}",
                    "endpoint": path,
                    "request_params": request_params,
                })
                failed += 1

            except Exception as exc:
                elapsed_ms = round((time.time() - start_time) * 1000)
                logger.error("%s %s?branch=%s -> unexpected error -> %sms", method, path, branch_code, elapsed_ms)
                results.append({
                    "branchCode": branch_code,
                    "branchName": branch["branchName"],
                    "success": False,
                    "status_code": None,
                    "execution_time_ms": elapsed_ms,
                    "error": f"Unexpected error: {str(exc)}",
                    "endpoint": path,
                    "request_params": request_params,
                })
                failed += 1

            if RISTA_REQUEST_DELAY > 0:
                time.sleep(RISTA_REQUEST_DELAY)

        _update_task(
            task,
            status="completed",
            progress="Completed",
            results=results,
            successful=successful,
            failed=failed,
            consolidated=_consolidate_branch_results(results),
        )

    except Exception as exc:
        logger.error("Iterate by branch failed unexpectedly: %s", exc)
        _update_task(task, status="failed", error=f"Unexpected error: {str(exc)}")


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
