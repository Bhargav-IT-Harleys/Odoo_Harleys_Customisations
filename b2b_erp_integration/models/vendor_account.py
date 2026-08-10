from odoo import api, fields, models


class VendorAccount(models.Model):
    _name = 'vendor.account'
    _description = 'Vendor Account'
    _order = 'name'

    name = fields.Char(required=True)
    platform_id = fields.Many2one('vendor.platform', required=True, string='Platform')
    vendor_partner_id = fields.Many2one(
        'res.partner',
        string='Vendor Partner',
        domain=[('supplier_rank', '>', 0)],
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor Partner',
        related='vendor_partner_id',
        store=True,
        readonly=False,
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    account_id = fields.Char(string='Account ID', required=True, copy=False)
    client_name = fields.Char(string='Client Name')
    mobile_number = fields.Char(string='Mobile Number')
    api_access_key = fields.Char(string='API Access Key')
    base_url = fields.Char(string='Base URL', default='https://devapi.hyperpure.com')
    auth_url = fields.Char(string='Auth URL')
    order_url = fields.Char(string='Order URL')
    webhook_url = fields.Char(string='Webhook URL')
    access_token = fields.Char(string='Access Token')
    otp_verified = fields.Boolean(readonly=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_account_per_platform_company', 'unique(account_id, platform_id, company_id)', 'An account ID must be unique per platform and company.'),
    ]

    @api.model
    def get_active_account(self, vendor_code=False, company=False, partner=False):
        domain = [('active', '=', True)]
        if vendor_code:
            domain.append(('platform_id.code', '=', vendor_code))
        if company:
            domain.append(('company_id', '=', company.id))
        if partner:
            domain.append(('vendor_partner_id', '=', partner.id))
        return self.search(domain, limit=1)
