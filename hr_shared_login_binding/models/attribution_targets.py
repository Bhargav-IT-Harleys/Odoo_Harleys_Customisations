"""Applies hr.employee.attribution.mixin to every business-transaction model
this module logs employee attribution for. To add another model: inherit it
here (and add its owning module to __manifest__.py depends if needed).
"""
from odoo import models


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _inherit = ['purchase.order', 'hr.employee.attribution.mixin']


class IndentRequest(models.Model):
    _name = 'indent.request'
    _inherit = ['indent.request', 'hr.employee.attribution.mixin']


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'hr.employee.attribution.mixin']


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'hr.employee.attribution.mixin']


class AccountPayment(models.Model):
    _name = 'account.payment'
    _inherit = ['account.payment', 'hr.employee.attribution.mixin']


class StockPicking(models.Model):
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'hr.employee.attribution.mixin']


class StockScrap(models.Model):
    _name = 'stock.scrap'
    _inherit = ['stock.scrap', 'hr.employee.attribution.mixin']


class MrpProduction(models.Model):
    _name = 'mrp.production'
    _inherit = ['mrp.production', 'hr.employee.attribution.mixin']


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = ['helpdesk.ticket', 'hr.employee.attribution.mixin']
