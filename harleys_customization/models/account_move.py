from odoo import models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        for move in self:
            if move.move_type != "in_invoice":
                continue

            # Bill Reference is mandatory
            if not move.ref or not move.ref.strip():
                raise ValidationError(
                    _("The Bill Reference field is mandatory before posting the Vendor Bill.")
                )

            # Bill Date is mandatory
            if not move.invoice_date:
                raise ValidationError(
                    _("The Bill Date is mandatory before posting the Vendor Bill.")
                )

            # Check duplicate Bill Reference for the same vendor
            duplicate = self.search([
                ("id", "!=", move.id),
                ("move_type", "=", "in_invoice"),
                ("partner_id", "=", move.partner_id.id),
                ("ref", "=", move.ref.strip()),
                ("state", "!=", "cancel"),
            ], limit=1)

            if duplicate:
                raise ValidationError(
                    _("Bill Reference '%s' already exists for vendor '%s'.")
                    % (move.ref, move.partner_id.display_name)
                )

        return super().action_post()