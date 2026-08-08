from odoo import fields, models


class ResGroups(models.Model):
    _name = 'res.groups'
    # No chatter in core, same gap res.users had - see res_users.py.
    _inherit = ['res.groups', 'mail.thread']

    name = fields.Char(tracking=True)
    user_ids = fields.Many2many(tracking=True)
