# -*- coding: utf-8 -*-
from odoo import models, api
from odoo import api, fields, models, _

class ProductCategory(models.Model):
    _inherit = 'product.category'

    property_stock_valuation_account_id = fields.Many2one(
        'account.account', 'Stock Valuation Account', company_dependent=True, ondelete='restrict',
        check_company=True, store=True,
        help="""When automated inventory valuation is enabled on a product, this account will hold the current value of the products.""")

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('sync_accounts_done'):
            return res

        income_id = vals.get('property_account_income_categ_id')
        expense_id = vals.get('property_account_expense_categ_id')
        routes = vals.get('route_ids')
        costing_method = vals.get('property_cost_method')
        removal_strategy = vals.get('removal_strategy_id')
        inventory_valuation = vals.get('property_valuation')
        reserve_packagings = vals.get('packaging_reserve_method')
        stock_valuation = vals.get('property_stock_valuation_account_id')

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
                if routes is not None:
                    sync_vals['route_ids'] = routes
                if costing_method is not None:
                    sync_vals['property_cost_method'] = costing_method
                if removal_strategy is not None:
                    sync_vals['removal_strategy_id'] = removal_strategy
                if inventory_valuation is not None:
                    sync_vals['property_valuation'] = inventory_valuation
                if reserve_packagings is not None:
                    sync_vals['packaging_reserve_method'] = reserve_packagings
                if stock_valuation is not None:
                    sync_vals['property_stock_valuation_account_id'] = stock_valuation
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
        routes = vals.get('route_ids')
        costing_method = vals.get('property_cost_method')
        removal_strategy = vals.get('removal_strategy_id')
        inventory_valuation = vals.get('property_valuation')
        reserve_packagings = vals.get('packaging_reserve_method')
        stock_valuation = vals.get('property_stock_valuation_account_id')

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
            if routes is not None:
                sync_vals['route_ids'] = routes
            if costing_method is not None:
                sync_vals['property_cost_method'] = costing_method
            if removal_strategy is not None:
                sync_vals['removal_strategy_id'] = removal_strategy
            if inventory_valuation is not None:
                sync_vals['property_valuation'] = inventory_valuation
            if reserve_packagings is not None:
                sync_vals['packaging_reserve_method'] = reserve_packagings
            if stock_valuation is not None:
                sync_vals['property_stock_valuation_account_id'] = stock_valuation
            target_category.with_company(company).with_context(sync_accounts_done=True).write(sync_vals)

