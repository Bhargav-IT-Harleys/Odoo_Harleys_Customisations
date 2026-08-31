from ...common.exceptions import ConfigurationError, PayloadError
from ...common.vendor_mapping import VendorProductMapper
from .constants import HyperpureConstants
from .exceptions import ProductError


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


class HyperpureMappingService:
    """Builds Hyperpure's real placeOrder payload shape (outlet_id/outlet_type/
    products[]/external_order_id) from an Odoo purchase order.

    The vendor's own product identifier is read from product.supplierinfo's
    built-in `product_code` field (Odoo's standard "vendor product code"),
    not a custom field - Hyperpure's product_number is exactly that concept."""

    REQUIRED_SUPPLIERINFO_FIELDS = ("product_code",)

    @staticmethod
    def build_order_payload(config, purchase_order, outlet=None, omit_price_product_codes=None):
        purchase_order.ensure_one()

        if not outlet:
            outlet = config.outlet_ids.filtered("active")[:1]
        if not outlet:
            raise ConfigurationError(
                f"No active outlet configured for vendor account '{config.name}'."
            )

        if not purchase_order.order_line:
            raise PayloadError("This purchase order has no order lines to send.")

        omit_price_product_codes = omit_price_product_codes or set()
        products = []
        for line in purchase_order.order_line:
            supplierinfo = VendorProductMapper.find_supplierinfo(line.product_id, config)
            mapping_errors = VendorProductMapper.validate_mapping(
                supplierinfo, line.product_id, config, HyperpureMappingService.REQUIRED_SUPPLIERINFO_FIELDS
            )
            if mapping_errors:
                raise ProductError(" ".join(error["message"] for error in mapping_errors))

            product_entry = {
                "product_number": supplierinfo.product_code,
                "product_type": HyperpureConstants.PRODUCT_TYPE,
                # Odoo's product_qty is a float (e.g. 8.0); their sample
                # payloads always show a bare integer ("quantity": 1) - send
                # int, not float-with-decimal-point, in case their schema
                # validation is strict about it. round() not int(), so a
                # genuinely fractional qty doesn't get silently truncated
                # down - Hyperpure's line items are whole units regardless.
                "quantity": int(round(line.product_qty)),
            }
            # reference_price is optional per Hyperpure's doc - omitting it
            # for a line the user explicitly chose to send "without price
            # match" lets Hyperpure price that line at its own live catalog
            # price instead of validating against ours.
            if supplierinfo.product_code not in omit_price_product_codes:
                product_entry["reference_price"] = line.price_unit
            products.append(product_entry)

        # delivery_date is intentionally omitted: Hyperpure assigns its own
        # Target Delivery Date (TDD) per outlet, which we have no way to know
        # in advance from any API we call - sending our own date and having
        # it mismatch their TDD gets the whole order rejected (confirmed
        # live). The field is optional per their doc, so leaving it out lets
        # Hyperpure use its own assigned TDD instead of guessing.
        return {
            "outlet_id": _as_int(outlet.outlet_id),
            "outlet_type": HyperpureConstants.OUTLET_TYPE,
            "products": products,
            # Confirmed by the account-specific doc's request-body table:
            # "string or integer" - our PO name is non-numeric, matching
            # their example's integer type instead (our own numeric PO id).
            "external_order_id": purchase_order.id,
        }
