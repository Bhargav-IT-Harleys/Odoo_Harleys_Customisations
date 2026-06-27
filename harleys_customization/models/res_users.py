# -*- coding: utf-8 -*-

from odoo import Command, api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    bom_create_edit_access = fields.Boolean(
        string="BOM Create/ Edit Access",
        compute='_compute_bom_create_edit_access',
        inverse='_inverse_bom_create_edit_access',
    )

    def _get_bom_create_edit_group(self):
        return self.env.ref('harleys_customization.group_bom_create_edit_access')

    @api.depends('group_ids')
    def _compute_bom_create_edit_access(self):
        group = self._get_bom_create_edit_group()
        for user in self:
            user.bom_create_edit_access = group in user.group_ids

    def _inverse_bom_create_edit_access(self):
        group = self._get_bom_create_edit_group()
        for user in self:
            command = Command.link(group.id) if user.bom_create_edit_access else Command.unlink(group.id)
            user.write({'group_ids': [command]})
