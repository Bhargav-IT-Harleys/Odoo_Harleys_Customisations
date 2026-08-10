from odoo import models, fields


class ResUsers(models.Model):
    _name = 'res.users'
    # res.users has no chatter in core - it inherits res.partner (for
    # contact/address data) but not mail.thread. Adding mail.thread here is
    # what makes the tracking=True fields below actually generate messages,
    # gives this model a working <chatter/>, and (via message_attribution.py,
    # which extends mail.thread generically) picks up employee-attribution
    # tagging for free.
    _inherit = ['res.users', 'mail.thread']

    is_shared_login = fields.Boolean(
        string="Shared / Functional Login",
        tracking=True,
        help="Enable for role-based accounts used by more than one employee "
             "(e.g. Purchase Manager, Accountant). Anyone signing in to this "
             "account must additionally confirm their own employee login "
             "before the session is granted, so actions can still be traced "
             "back to the person, not just the role.")
    authorized_employee_ids = fields.Many2many(
        'hr.employee',
        'res_users_authorized_employee_rel',
        'user_id', 'employee_id',
        string="Authorized Employees",
        tracking=True,
        help="Employees authorized to use this shared login."
             "At least one employee must be selected to allow access to this account.")

    def _mfa_type(self):
        # Chain rather than override: an account that already has another
        # MFA method configured (e.g. auth_totp) keeps using it.
        existing = super()._mfa_type()
        if existing:
            return existing
        # Called by core during the initial login POST, before any session
        # exists (env.user is Public at that point) - must read via sudo,
        # same as auth_totp does for its own MFA fields.
        if self.sudo().is_shared_login:
            return 'employee_verify'
        return existing

    def _mfa_url(self):
        existing = super()._mfa_url()
        if existing:
            return existing
        if self.sudo().is_shared_login:
            return '/web/login/employee_verify'
        return existing
