# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_STATE = [('draft','Draft'),('sent','Sent'),('approved', 'Approved'),('rejected','Rejected')]

class ResPartner(models.Model):
    _inherit = 'res.partner'

    state = fields.Selection(_STATE, default="draft", string="Status", readonly="1", copy=False, tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True, copy=False)
    approved_date = fields.Datetime(
        string='Approved Date',
        readonly=True,
        tracking=True,
        copy=False,
    )

    def action_sent(self):
        if self.state in ('draft', 'rejected'):
            self.state = 'sent'

    def action_approve(self):
        if self.state in ('sent'):
            self.state = 'approved'
            self.active = True
            self.approved_by = self.env.user.id
            self.approved_date = fields.Datetime.now()


    def action_reject(self):
        if self.state in ('sent'):
            self.state = 'rejected'


    @api.constrains('ref')
    def _check_ref_unique(self):
        for record in self:
            if record.ref:
                duplicate = self.env['res.partner'].search([
                    ('ref', '=', record.ref),
                    ('id', '!=', record.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(f'Reference "{record.ref}" already exists. Reference field must be unique.')



    def _get_complete_name(self):
        self.ensure_one()
        name = self.name or ''
        if self.ref:
            name = f"{self.ref}, {name}"
        return name.strip()
    
    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for val in vals:
                val['active'] = False
        else:
            vals['active'] = False 
        return super(ResPartner, self).create(vals)


    def make_state_as_sent(self):
        for record in self:
            record.state = 'sent'
            record.active = False