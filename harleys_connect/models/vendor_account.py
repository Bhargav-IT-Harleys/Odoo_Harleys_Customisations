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
    mobile_number = fields.Char(
        string='Mobile Number',
        help="Informational only - the OTP flow authenticates against a "
             "user_id (picked from the outlet's registered phone numbers), "
             "not this field directly.",
    )
    user_id = fields.Char(
        string='Auth User ID',
        copy=False,
        groups='harleys_connect.group_connect_manager',
        help="The Hyperpure user_id last used to authenticate this account "
             "(from the outlet_phone_numbers lookup).",
    )
    api_access_key = fields.Char(string='API Access Key', groups='harleys_connect.group_connect_manager')
    base_url = fields.Char(string='Base URL', default='https://devapi.hyperpure.com')
    auth_url = fields.Char(string='Auth URL')
    order_url = fields.Char(string='Order URL')
    webhook_url = fields.Char(string='Webhook URL')
    webhook_api_key = fields.Char(
        string='Webhook API Key',
        groups='harleys_connect.group_connect_manager',
        help="Separate credential Hyperpure issues specifically for webhook "
             "delivery - not the same as the API Access Key above.",
    )
    access_token = fields.Char(string='Access Token', groups='harleys_connect.group_connect_manager')
    otp_verified = fields.Boolean(readonly=True)
    active = fields.Boolean(default=True)
    outlet_ids = fields.One2many('vendor.outlet', 'vendor_account_id', string='Outlets')

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

    def resolve_outlet(self, warehouse=False):
        """Returns (outlet_recordset, is_ambiguous). Auto-resolves when
        there's nothing to choose (0 or 1 active outlets - today's implicit
        behaviour) or when exactly one active outlet's warehouse_id matches
        the given warehouse; otherwise returns all active outlets with
        is_ambiguous=True so the caller (the send-to-vendor wizard) can ask
        the user to pick."""
        self.ensure_one()
        outlets = self.outlet_ids.filtered("active")
        if len(outlets) <= 1:
            return outlets, False
        if warehouse:
            matches = outlets.filtered(lambda o: o.warehouse_id == warehouse)
            if len(matches) == 1:
                return matches, False
        return outlets, True

    def action_authenticate(self):
        """Opens the OTP wizard bound to this account only - authenticating
        is a one-time (well, once-per-60-days) account-level action, not tied
        to any specific purchase order."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Authenticate Vendor Account",
            "res_model": "vendor.auth.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_account_id": self.id,
                "default_user_id": self.user_id,
            },
        }
