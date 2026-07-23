"""Fallback log for deletions with no parent document to log to - see
message_attribution.py's _log_attribution_deletion(). Not mail.thread-based
(it is the log; logging to it would be circular), and only ever written to
via that fallback, never created by hand.
"""
from odoo import fields, models


class HrAttributionLog(models.Model):
    _name = 'hr.attribution.log'
    _description = "Employee Attribution Log (fallback for deletions with no parent to log to)"
    _order = 'logged_at desc'
    _log_access = False

    employee_id = fields.Many2one('hr.employee', string="Employee", required=True, index=True)
    user_id = fields.Many2one('res.users', string="Account", required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    res_model = fields.Char(string="Model", required=True, index=True)
    res_id = fields.Integer(string="Record ID", required=True)
    record_name = fields.Char(string="Record")
    action = fields.Selection([
        ('deleted', "Deleted"),
    ], string="Action", required=True, default='deleted')
    logged_at = fields.Datetime(string="Logged At", default=fields.Datetime.now, required=True)
