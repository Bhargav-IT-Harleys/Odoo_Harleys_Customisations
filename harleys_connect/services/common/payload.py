_REDACTED_KEYS = {"password", "secret", "secret_key", "token", "access_token", "refresh_token", "api_key", "api_access_key", "otp"}


def redact_payload(data):
    """Recursively blank out credential-shaped values before they're written to a
    log table, so vendor.api.log never stores a raw secret even if a future
    adapter's request/response body happens to include one."""
    if isinstance(data, dict):
        return {
            key: ("***REDACTED***" if key.lower() in _REDACTED_KEYS else redact_payload(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [redact_payload(item) for item in data]
    return data


def build_default_payload(purchase_order):
    lines = []
    for line in purchase_order.order_line:
        lines.append({
            "product": line.product_id.display_name,
            "qty": line.product_qty,
            "price": line.price_unit,
            "uom": line.product_uom.name,
        })

    return {
        "po_number": purchase_order.name,
        "vendor": purchase_order.partner_id.name,
        "lines": lines,
    }
