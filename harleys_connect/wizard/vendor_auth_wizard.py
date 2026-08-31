# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.harleys_connect.services.common.exceptions import IntegrationError
from odoo.addons.harleys_connect.services.manager import VendorIntegrationManager


class VendorAuthWizard(models.TransientModel):
    _name = "vendor.auth.wizard"
    _description = "Vendor Authentication"

    account_id = fields.Many2one(
        "vendor.account",
        required=True,
        string="Vendor Account",
    )

    user_id = fields.Char(
        string="User ID",
        help="Pick the user_id matching the phone number to send the OTP to, "
             "from the list below (Get Registered Phones).",
    )

    available_phone_numbers = fields.Text(
        string="Registered Phone Numbers",
        readonly=True,
    )

    otp = fields.Char(string="OTP")

    def action_fetch_phones(self):
        self.ensure_one()
        account = self.account_id

        outlet = self.env["vendor.outlet"].search([
            ("vendor_account_id", "=", account.id),
            ("active", "=", True),
        ], limit=1)
        if not outlet:
            raise UserError("No active outlet configured for this vendor account.")

        manager = VendorIntegrationManager(account)
        try:
            response = manager.get_outlet_phone_numbers(outlet.outlet_id)
        except IntegrationError as exc:
            raise UserError(str(exc)) from exc

        try:
            body = response.json()
        except ValueError:
            body = {}
        contacts = ((body.get("response") or {}).get("masked_contacts")) or []
        self.available_phone_numbers = (
            "\n".join(f"{c.get('phone_number')} -> user_id: {c.get('user_id')}" for c in contacts)
            if contacts else "No registered phone numbers found for this outlet."
        )

        # A button inside a target="new" dialog that returns nothing/falsy is
        # treated as "close the dialog" - re-open this same wizard record
        # explicitly so it stays open with the fetched list visible.
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "vendor.auth.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_send_otp(self):
        self.ensure_one()
        if not self.user_id:
            raise UserError("Enter the user_id from the registered phone numbers list first.")

        manager = VendorIntegrationManager(self.account_id)
        try:
            manager.request_otp(user_id=self.user_id)
        except IntegrationError as exc:
            raise UserError(str(exc)) from exc

        self.account_id.write({"user_id": self.user_id})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "OTP Sent",
                "message": "An OTP has been sent for user_id %s." % self.user_id,
                "type": "success",
                "sticky": False,
            },
        }

    def action_verify(self):
        self.ensure_one()
        if not self.otp:
            raise UserError("Enter the OTP you received.")
        if not self.user_id:
            raise UserError("Enter the user_id and send an OTP first.")

        manager = VendorIntegrationManager(self.account_id)
        try:
            manager.verify_otp(self.otp, user_id=self.user_id)
        except IntegrationError as exc:
            raise UserError(str(exc)) from exc

        self.account_id.write({"otp_verified": True, "user_id": self.user_id})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Authenticated",
                "message": "The vendor account is authenticated and ready to send orders.",
                "type": "success",
                "sticky": False,
            },
        }
