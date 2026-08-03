from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    purchase_type = fields.Selection([('x_p_o', 'Purchase Order (External PO)'), ('i_p_o', 'Internal Transfer (Internal PO)')], string='Purchase type')

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.constrains('ref', 'partner_id', 'move_type')
    def _check_unique_ref_per_vendor(self):
        for bill in self:
            if (
                bill.move_type != 'in_invoice'
                or not bill.ref
                or not bill.partner_id
            ):
                continue
            duplicate_bills = self.sudo().search([
                ('id', '!=', bill.id),
                ('move_type', '=', 'in_invoice'),
                ('partner_id', '=', bill.partner_id.id),
                ('ref', '=', bill.ref),
            ])
            if duplicate_bills:
                bill_names = ", ".join(
                    duplicate_bills.mapped("display_name")
                )
                raise ValidationError(_(
                    "The Vendor Bill Reference '%(ref)s' has already been used "
                    "for vendor '%(vendor)s'.\n\n"
                    "Company: %(company)s\n"
                    "Existing Bill(s): %(bills)s"
                ) % {
                    'ref': bill.ref,
                    'vendor': bill.partner_id.display_name,
                    'company': duplicate_bills[0].company_id.display_name,
                    'bills': bill_names,
                })