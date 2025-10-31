# -*- coding: utf-8 -*-
from odoo import models, api

class ProductCategory(models.Model):
    _inherit = 'product.category'

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('sync_accounts_done'):
            return res

        income_id = vals.get('property_account_income_categ_id')
        expense_id = vals.get('property_account_expense_categ_id')

        companies = self.env['res.company'].search([])
        for category in self:
            for company in companies:
                target_category = self.with_context(company_id=company.id).search([
                    ('name', '=', category.name)
                ], limit=1)
                if not target_category:
                    continue

                sync_vals = {}
                if income_id is not None:
                    sync_vals['property_account_income_categ_id'] = income_id
                if expense_id is not None:
                    sync_vals['property_account_expense_categ_id'] = expense_id

                target_category.with_company(company).with_context(sync_accounts_done=True).write(sync_vals)
        return res
