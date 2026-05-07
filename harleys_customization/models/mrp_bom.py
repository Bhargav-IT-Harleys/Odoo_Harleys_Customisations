# -*- coding: utf-8 -*-

from odoo import fields, models, api


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

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for val in vals:
                val['active'] = False
        else:
            vals['active'] = False 
        return super(MrpBom, self).create(vals)


    def make_state_as_sent(self):
        for record in self:
            record.state = 'sent'
            record.active = False