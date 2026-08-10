from odoo import fields, models


class VendorOutlet(models.Model):
    _name = 'vendor.outlet'
    _description = 'Vendor Outlet'
    _order = 'name'

    name = fields.Char(string='Outlet Name', required=True)
    vendor_account_id = fields.Many2one('vendor.account', string='Vendor Account', required=True, ondelete='cascade')
    outlet_id = fields.Char(string='Outlet ID', required=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    partner_id = fields.Many2one('res.partner', string='Partner')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_outlet_per_account', 'unique(vendor_account_id, outlet_id)', 'An outlet ID must be unique per vendor account.'),
    ]
