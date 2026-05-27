# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    partner_id = fields.Many2one(context={'active_test': False})
