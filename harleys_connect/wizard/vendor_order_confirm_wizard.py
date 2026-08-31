# -*- coding: utf-8 -*-

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.harleys_connect.services.common.exceptions import IntegrationError
from odoo.addons.harleys_connect.services.common.vendor_mapping import VendorProductMapper
from odoo.addons.harleys_connect.services.manager import VendorIntegrationManager


class VendorOrderConfirmWizard(models.TransientModel):
    _name = "vendor.order.confirm.wizard"
    _description = "Confirm Vendor Order"

    purchase_order_id = fields.Many2one("purchase.order", required=True)
    account_id = fields.Many2one("vendor.account", required=True)
    outlet_id = fields.Many2one(
        "vendor.outlet",
        # Not required at the field/ORM level: when the outlet is ambiguous
        # (multiple outlets, no warehouse match), the wizard is created with
        # this blank on purpose so the user can pick one - enforced instead
        # in action_confirm_send, right before it would actually matter.
        domain="[('vendor_account_id', '=', account_id)]",
        help="Which outlet this order is placed at - always shown so it's "
             "never ambiguous which physical location an order is going to.",
    )
    line_ids = fields.One2many("vendor.order.confirm.wizard.line", "wizard_id")
    price_check_done = fields.Boolean(readonly=True)
    price_check_summary = fields.Text(readonly=True)
    has_price_mismatch = fields.Boolean(compute="_compute_has_price_mismatch")
    send_without_price_match = fields.Boolean(
        string="Send without price match",
        help="Allow sending even though one or more lines don't match the "
             "vendor's live price. For those lines only, our price is left "
             "out of the request entirely, so the vendor prices them at "
             "their own live catalog price instead of rejecting the order.",
    )

    @api.depends("line_ids.price_mismatch")
    def _compute_has_price_mismatch(self):
        for wizard in self:
            wizard.has_price_mismatch = bool(wizard.line_ids.filtered("price_mismatch"))

    def open_for_order(self, purchase_order, account):
        """Entry point called from purchase.order.action_send_to_vendor -
        resolves the outlet, builds the line grid, and runs the price check
        up front so the comparison is visible the moment the dialog opens."""
        outlets, is_ambiguous = account.resolve_outlet(purchase_order.picking_type_id.warehouse_id)
        outlet = outlets[:1] if not is_ambiguous else self.env["vendor.outlet"]

        line_vals = []
        for line in purchase_order.order_line:
            supplierinfo = VendorProductMapper.find_supplierinfo(line.product_id, account)
            line_vals.append(Command.create({
                "product_id": line.product_id.id,
                "product_qty": line.product_qty,
                "our_price": line.price_unit,
                "vendor_product_code": supplierinfo.product_code if supplierinfo else False,
            }))

        wizard = self.create({
            "purchase_order_id": purchase_order.id,
            "account_id": account.id,
            "outlet_id": outlet.id if outlet else False,
            "line_ids": line_vals,
        })
        wizard._fetch_prices()
        return wizard._reopen()

    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "vendor.order.confirm.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _fetch_prices(self):
        self.ensure_one()
        codes = [line.vendor_product_code for line in self.line_ids if line.vendor_product_code]
        if not self.outlet_id or not codes:
            return

        manager = VendorIntegrationManager(self.account_id)
        try:
            results = manager.search_products(self.outlet_id.outlet_id, product_numbers=codes)
        except IntegrationError as exc:
            # Fail open: an unreachable price-lookup endpoint is a different
            # failure mode than a confirmed mismatch - the vendor's own
            # server-side price check is still the real guard, so a broken
            # check here must not block sending.
            self.price_check_summary = "Price check unavailable: %s" % exc
            return

        prices_by_code = {result["product_number"]: result["price"] for result in results}
        for line in self.line_ids:
            price = prices_by_code.get(line.vendor_product_code)
            if price is None:
                continue
            mismatch = round(abs(price - line.our_price), 2) > 0
            line.write({
                "vendor_price": price,
                "price_mismatch": mismatch,
                "mismatch_note": (
                    "Vendor price ₹%.2f differs from our price ₹%.2f" % (price, line.our_price)
                    if mismatch else False
                ),
            })
        self.price_check_done = True
        self.price_check_summary = False

    def action_check_prices(self):
        self.ensure_one()
        self._fetch_prices()
        return self._reopen()

    def action_confirm_send(self):
        self.ensure_one()
        if not self.outlet_id:
            raise UserError("Select which outlet this order is for before sending.")

        mismatched = self.line_ids.filtered("price_mismatch")
        if mismatched and not self.send_without_price_match:
            names = ", ".join(mismatched.mapped("product_id.display_name"))
            raise UserError(
                "These products don't match the vendor's live price: %s. "
                "Update the purchase order price, or tick 'Send without "
                "price match' to send those lines at the vendor's own price."
                % names
            )

        omit_codes = set(mismatched.mapped("vendor_product_code")) if self.send_without_price_match else None
        return self.purchase_order_id._send_to_vendor(self.account_id, self.outlet_id, omit_price_product_codes=omit_codes)
