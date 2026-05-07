# -*- coding: utf-8 -*-

from odoo import fields, models


_STATE = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    state = fields.Selection(
        _STATE,
        default='draft',
        string='Status',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        tracking=True,
        copy=False,
    )
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        tracking=True,
        copy=False,
    )

    def action_sent(self):
        for bom in self:
            if bom.state in ('draft', 'rejected'):
                bom.write({
                    'state': 'sent',
                    'approved_by': False,
                    'approved_date': False,
                })

    def action_approve(self):
        for bom in self:
            if bom.state == 'sent':
                bom.write({
                    'state': 'approved',
                    'active': True,
                    'approved_by': self.env.user.id,
                    'approved_date': fields.Datetime.now(),
                })

    def action_reject(self):
        for bom in self:
            if bom.state == 'sent':
                bom.write({
                    'state': 'rejected',
                    'approved_by': False,
                    'approved_date': False,
                })
