from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    legal_name = fields.Char(compute='_compute_legal_name', store=True, readonly=False, groups="hr.group_hr_user,base.group_portal")
    registration_number = fields.Char('Employee Reference', groups="hr.group_hr_user,base.group_portal", copy=False, tracking=True)
    version_id = fields.Many2one(
        'hr.version',
        compute='_compute_version_id',
        search='_search_version_id',
        ondelete='cascade',
        required=True,
        store=False,
        compute_sudo=True,
        groups="hr.group_hr_user,base.group_portal")
    contract_date_start = fields.Date(readonly=False, related="version_id.contract_date_start", inherited=True, groups="hr.group_hr_manager,base.group_portal")
    l10n_in_uan = fields.Char(string='UAN', groups="hr.group_hr_user,base.group_portal", copy=False)
    l10n_in_pan = fields.Char(string='PAN', groups="hr.group_hr_user,base.group_portal", copy=False)
    l10n_in_esic_number = fields.Char(string='ESIC Number', groups="hr.group_hr_user,base.group_portal", copy=False)
    bank_account_ids = fields.Many2many(
        'res.partner.bank',
        relation='employee_bank_account_rel',
        column1='employee_id',
        column2='bank_account_id',
        domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        groups="hr.group_hr_user,base.group_portal",
        tracking=True,
        string='Bank Accounts',
        help='Employee bank accounts to pay salaries')