from odoo import api, fields, models


class VendorAccount(models.Model):
    _name = 'vendor.account'
    _description = 'Vendor Account'
    _order = "name"

    name = fields.Char(required=True)
    platform_id = fields.Many2one('vendor.platform', required=True)
    partner_id = fields.Many2one('res.partner', string='Vendor Partner')
    account_type = fields.Selection([
        ('api', 'API'),
        ('webhook', 'Webhook'),
    ], default='api')
    mobile_number = fields.Char()
    outlet_id = fields.Char(string='Outlet ID')
    vendor_code = fields.Char()
    base_url = fields.Char()
    auth_url = fields.Char()
    order_url = fields.Char()
    webhook_url = fields.Char()
    access_token = fields.Char()
    otp_verified = fields.Boolean(readonly=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model
    def get_active_account(self, vendor_code=False, company=False, partner=False):
        domain = [('active', '=', True)]
        if vendor_code:
            domain.append(('platform_id.code', '=', vendor_code))
        if company:
            domain.append(('company_id', '=', company.id))
        if partner:
            domain.append(('partner_id', '=', partner.id))
        return self.search(domain, limit=1)
