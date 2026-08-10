class HyperpureMappingService:
    """Build Hyperpure-specific payloads from Odoo records."""

    @staticmethod
    def build_order_payload(purchase_order):
        purchase_order.ensure_one()
        lines = []
        for line in purchase_order.order_line:
            supplierinfo = HyperpureMappingService._get_supplierinfo(line)
            lines.append({
                "product": line.product_id.display_name,
                "vendor_product_code": supplierinfo.vendor_product_code if supplierinfo else False,
                "vendor_product_id": supplierinfo.vendor_product_id if supplierinfo else False,
                "qty": line.product_qty,
                "price": line.price_unit,
                "uom": supplierinfo.vendor_uom_code if supplierinfo and supplierinfo.vendor_uom_code else line.product_uom_id.name,
            })

        return {
            "po_number": purchase_order.name,
            "vendor": purchase_order.partner_id.name,
            "lines": lines,
        }

    @staticmethod
    def _get_supplierinfo(line):
        supplierinfos = line.product_id.seller_ids.filtered(
            lambda seller: seller.partner_id == line.order_id.partner_id
        )
        return supplierinfos[:1] if supplierinfos else False
