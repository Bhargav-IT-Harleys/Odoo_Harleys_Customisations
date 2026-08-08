"""Master-data models with no chatter in core, retrofitted with mail.thread
so employee-attribution logging (message_attribution.py) has somewhere to
post. None of them get per-field tracking=True - too many fields, or no
single field that matters more than the others - so they rely entirely on
the "Log Every Change"/"Log Deletions" catch-all (attribution_config.py),
pre-enabled by data/attribution_config_data.xml.

res.users, res.groups and hr.employee live in their own files instead -
they carry actual per-field tracking=True and other logic, not just this
mixin.
"""
from odoo import models


class ResCompany(models.Model):
    _name = 'res.company'
    _inherit = ['res.company', 'mail.thread']


class StockLocation(models.Model):
    _name = 'stock.location'
    _inherit = ['stock.location', 'mail.thread']


class StockWarehouse(models.Model):
    _name = 'stock.warehouse'
    _inherit = ['stock.warehouse', 'mail.thread']


class StockPickingType(models.Model):
    _name = 'stock.picking.type'
    _inherit = ['stock.picking.type', 'mail.thread']


class StockRoute(models.Model):
    _name = 'stock.route'
    _inherit = ['stock.route', 'mail.thread']


class StockStorageCategory(models.Model):
    _name = 'stock.storage.category'
    _inherit = ['stock.storage.category', 'mail.thread']
