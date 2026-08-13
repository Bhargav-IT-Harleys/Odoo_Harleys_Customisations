from odoo import fields, models


class ResUsers(models.Model):
    _name = 'res.users'
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
        existing = super()._mfa_type()
        if existing:
            return existing
        if self.sudo().is_shared_login:
            return 'employee_verify'
        return existing

    def _get_auth_methods(self):
        return [
            method for method in super()._get_auth_methods()
            if method != 'employee_verify'
        ]

    def _mfa_url(self):
        existing = super()._mfa_url()
        if existing:
            return existing
        if self.sudo().is_shared_login:
            return '/web/login/employee_verify'
        return existing
