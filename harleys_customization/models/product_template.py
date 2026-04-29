# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_STATE = [('draft','Draft'),('sent','Sent'),('approved', 'Approved'),('rejected','Rejected')]

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    state = fields.Selection(_STATE, default="draft", string="Status", readonly="1", copy=False, tracking=True)
    approved_by = fields.Many2one('res.users', string='Approved By', tracking=True, copy=False)
    batch_size = fields.Float(string="Batch Size")
    section = fields.Many2one('production.section', string="Production Section")

    def action_sent(self):
        if self.state in ('draft', 'rejected'):
            self.state = 'sent'

    def action_approve(self):
        if self.state in ('sent'):
            self.state = 'approved'
            self.active = True
            self.approved_by = self.env.user.id

    def action_reject(self):
        if self.state in ('sent'):
            self.state = 'rejected'

    @api.model
    def create(self, vals):
        if isinstance(vals, list):
            for val in vals:
                val['active'] = False
        else:
            vals['active'] = False 
        return super(ProductTemplate, self).create(vals)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    # batch_size = fields.Float(string="Batch Size")
    # section = fields.Many2one('production.section', string="Production Section")

    # @api.model
    # def create(self, vals):
    #     rec = super().create(vals)
    #     if rec.section:
    #         rec.product_tmpl_id.write({
    #             'section': rec.section.id
    #         })

    #     return rec

    # def write(self, vals):
    #     res = super().write(vals)
    #     if 'section' in vals:
    #         for rec in self:
    #             rec.product_tmpl_id.write({
    #                 'section': rec.section.id
    #             })

    #     return res

class ProductionSection(models.Model):
    _name = "production.section"
    _description = "Production Section"

    name = fields.Char(string="Production Section")
    code = fields.Char(string="Code / Type")
