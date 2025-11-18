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

    def create(self, vals):
        # Handle batch create (list of dicts)
        if isinstance(vals, list):
            categories = super().create(vals)
            for category, val in zip(categories, vals):
                category._sync_accounts_on_create(val)
            return categories
        else:
            category = super().create(vals)
            category._sync_accounts_on_create(vals)
            return category

    def _sync_accounts_on_create(self, vals):
        if self.env.context.get('sync_accounts_done'):
            return

        income_id = vals.get('property_account_income_categ_id')
        expense_id = vals.get('property_account_expense_categ_id')

        if not income_id and not expense_id:
            return

        companies = self.env['res.company'].search([])
        for company in companies:
            target_category = self.with_context(company_id=company.id).search([
                ('name', '=', self.name)
            ], limit=1)

            if not target_category:
                continue

            sync_vals = {}
            if income_id is not None:
                sync_vals['property_account_income_categ_id'] = income_id
            if expense_id is not None:
                sync_vals['property_account_expense_categ_id'] = expense_id

            target_category.with_company(company).with_context(sync_accounts_done=True).write(sync_vals)

