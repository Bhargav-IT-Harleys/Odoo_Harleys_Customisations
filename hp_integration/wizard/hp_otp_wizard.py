# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class HyperpureOTPWizard(models.TransientModel):
    _name = "hp.otp.wizard"
    _description = "Hyperpure OTP Verification"

    purchase_order_id = fields.Many2one(
        "purchase.order",
        required=True,
    )

    configuration_id = fields.Many2one(
        "hp.configuration",
        required=True,
    )

    otp = fields.Char(
        required=True,
    )

    def action_verify(self):

        self.ensure_one()

        if len(self.otp) != 6:
            raise UserError(
                "OTP should contain 6 digits."
            )

        purchase = self.purchase_order_id

        payload = purchase.prepare_hyperpure_payload()

        # Actual API integration will be added in Batch 3.
        # For now we simulate success so the UI flow can be tested.

        purchase.write({
            "hp_order_sent": True,
            "hp_order_id": "TEST123456",
        })

        purchase.create_hp_log(
            self.configuration_id,
            payload,
            {
                "message": "Simulation Successful",
                "order_id": "TEST123456",
            },
            200,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Hyperpure",
                "message": "Purchase Order sent successfully (Simulation).",
                "type": "success",
                "sticky": False,
            },
        }