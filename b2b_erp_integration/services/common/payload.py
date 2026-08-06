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
