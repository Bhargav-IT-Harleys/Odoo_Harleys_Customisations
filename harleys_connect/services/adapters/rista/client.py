import json

from ...http_client import HttpClient
from ...common.exceptions import APIResponseError, ConfigurationError
from .auth import RistaAuthService
from .constants import REPORT_CATALOG_BY_ID, RistaConstants

_PREFERRED_LIST_KEYS = ["data.items", "items", "data", "records", "results"]


def _flatten_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


def normalize_response(response_body):
    """Turn an arbitrary Rista JSON response into a flat list of dict rows for
    display, without assuming a fixed shape - ported from rista_api_tester's
    _normalize_response(), which already solved this for the same API."""
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
            candidates.sort(key=lambda item: (
                0 if item[0] in _PREFERRED_LIST_KEYS else 1,
                _PREFERRED_LIST_KEYS.index(item[0]) if item[0] in _PREFERRED_LIST_KEYS else 999,
                item[0],
            ))
            _, records = candidates[0]

    elif isinstance(response_body, list):
        if response_body and isinstance(response_body[0], dict):
            records = response_body
        elif response_body:
            records = [{"value": value} for value in response_body]

    return [{key: _flatten_value(value) for key, value in record.items()} for record in records]


class RistaReportService:
    """Fetches a Rista report by catalog id and returns Odoo-display-ready rows."""

    @staticmethod
    def fetch_report(config, report_id, params=None):
        report = REPORT_CATALOG_BY_ID.get(report_id)
        if not report:
            raise ConfigurationError(f"Unknown Rista report '{report_id}'.")

        if not config.api_key or not config.secret_key:
            raise ConfigurationError(
                "Rista API key and secret key are not configured. "
                "Set them under Settings > Harley's Connect."
            )

        base_url = config.base_url or RistaConstants.DEFAULT_BASE_URL
        url = f"{base_url.rstrip('/')}{report['path']}"
        headers = RistaAuthService.get_auth_headers("GET", config.api_key, config.secret_key)

        query = {key: value for key, value in (params or {}).items() if value not in (None, "")}
        if query:
            from urllib.parse import urlencode
            url = f"{url}?{urlencode(query)}"

        response = HttpClient.get(url, headers)
        if response.status_code >= 400:
            raise APIResponseError(
                f"Rista API returned {response.status_code} for '{report['name']}': {response.text[:500]}"
            )

        try:
            body = response.json()
        except ValueError:
            body = {}

        rows = normalize_response(body)
        # The catalog's field_mapping (where present) lists the vendor's own nested
        # JSON paths, not this response's flattened top-level keys - not safe to use
        # as a re-keying shortcut, so columns are always derived from the actual
        # flattened rows rather than the catalog metadata.
        columns = sorted({key for row in rows for key in row.keys()})

        return {
            "report_id": report_id,
            "columns": columns,
            "rows": rows,
            "total": len(rows),
        }
