# -*- coding: utf-8 -*-
from odoo import models

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def write(self, vals):
        res = super().write(vals)

        if self.env.context.get('sync_accounts_done'):
            return res

        receivable_id = vals.get('property_account_receivable_id')
        payable_id = vals.get('property_account_payable_id')

        if not receivable_id and not payable_id:
            return res

        companies = self.env['res.company'].search([])
        for partner in self:
            for company in companies:
                target_partner = self.with_company(company).search([
                    ('id', '=', partner.id)
                ], limit=1)

                if not target_partner:
                    continue

                sync_vals = {}
                if receivable_id is not None:
                    sync_vals['property_account_receivable_id'] = receivable_id
                if payable_id is not None:
                    sync_vals['property_account_payable_id'] = payable_id

                target_partner.with_company(company).with_context(sync_accounts_done=True).write(sync_vals)

        return res

    def create(self, vals):
        if isinstance(vals, list):
            partners = super().create(vals)
            for partner, val in zip(partners, vals):
                partner._sync_accounts_on_create(val)
            return partners
        else:
            partner = super().create(vals)
            partner._sync_accounts_on_create(vals)
            return partner

    def _sync_accounts_on_create(self, vals):
        if self.env.context.get('sync_accounts_done'):
            return

        receivable_id = vals.get('property_account_receivable_id')
        payable_id = vals.get('property_account_payable_id')

        if not receivable_id and not payable_id:
            return

        companies = self.env['res.company'].search([])
        for company in companies:
            target_partner = self.with_company(company).search([
                ('id', '=', self.id)
            ], limit=1)

            if not target_partner:
                continue

            sync_vals = {}
            if receivable_id is not None:
                sync_vals['property_account_receivable_id'] = receivable_id
            if payable_id is not None:
                sync_vals['property_account_payable_id'] = payable_id

            target_partner.with_company(company).with_context(sync_accounts_done=True).write(sync_vals)

