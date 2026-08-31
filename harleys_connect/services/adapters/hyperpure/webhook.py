class HyperpureWebhookService:
    """Handles Hyperpure's order-sync webhook payload (official "External POS
    integration" spec, section "Order Event Payload"):
    {"external_entity": "HP", "orders": [{"order_number", "order_status",
    "external_order_id", "buyer_outlet_id", "order_items": [...], ...}]}
    """

    @staticmethod
    def verify_signature(config, headers):
        # Hyperpure issues a dedicated webhook API key, separate from the
        # ApiAccessKey used for outbound calls - confirmed in their spec.
        received = headers.get("x-hp-api-key") or headers.get("X-Hp-Api-Key")
        return bool(received) and bool(config.webhook_api_key) and received == config.webhook_api_key

    @staticmethod
    def handle(config, payload):
        return [HyperpureWebhookService._sync_order(config, order) for order in payload.get("orders", [])]

    @staticmethod
    def _sync_order(config, order):
        env = config.env
        order_number = order.get("order_number")
        external_order_id = order.get("external_order_id")
        status = order.get("order_status")

        # external_order_id is our own PO database id (sent as a bare integer
        # in build_order_payload, matching Hyperpure's documented example
        # type) - preferred match since it's guaranteed correct. Falls back to
        # matching by PO name for any order placed before this field became
        # numeric. order_number is Hyperpure's own id, only known to us once a
        # previous webhook has recorded it.
        purchase = env["purchase.order"]
        if external_order_id:
            try:
                purchase = purchase.search([("id", "=", int(external_order_id))], limit=1)
            except (TypeError, ValueError):
                pass
            if not purchase:
                purchase = purchase.search([("name", "=", str(external_order_id))], limit=1)
        if not purchase and order_number:
            purchase = env["purchase.order"].search(
                [("vendor_order_number", "=", str(order_number))], limit=1
            )

        if not purchase:
            return {"matched": False, "order_number": order_number, "status": status}

        purchase.write({
            "vendor_order_number": str(order_number) if order_number else purchase.vendor_order_number,
            "vendor_order_status": status or purchase.vendor_order_status,
        })
        return {"matched": True, "purchase_order_id": purchase.id, "order_number": order_number, "status": status}
