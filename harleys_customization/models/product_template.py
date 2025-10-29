# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_STATE = [('draft','Draft'),('sent','Sent'),('approved', 'Approved'),('rejected','Rejected')]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    state = fields.Selection(_STATE, default="draft", string="Status", readonly="1", copy=False, tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True, copy=False)


    def action_sent(self):
        if self.state in ('draft', 'rejected'):
            self.state = 'sent'

    def action_approve(self):
        if self.state in ('sent'):
            self.state = 'approved'
            self.approved_by = self.env.user.id

    def action_reject(self):
        if self.state in ('sent'):
            self.state = 'rejected'

