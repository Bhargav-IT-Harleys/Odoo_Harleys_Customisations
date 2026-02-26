from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    contract_date_start = fields.Date('Contract Start Date', tracking=True, groups="hr.group_hr_manager,base.group_portal")
    contract_date_end = fields.Date(
        'Contract End Date', tracking=True, help="End date of the contract (if it's a fixed-term contract).",
        groups="hr.group_hr_manager,base.group_portal")
    date_version = fields.Date(required=True, default=fields.Date.today, tracking=True, groups="hr.group_hr_user,base.group_portal")