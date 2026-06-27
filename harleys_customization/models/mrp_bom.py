# -*- coding: utf-8 -*-

from lxml import etree

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError


_STATE = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


def _check_bom_create_edit_access(env):
    if env.su or env.uid == SUPERUSER_ID:
        return
    if not env.user.has_group('harleys_customization.group_bom_create_edit_access'):
        raise AccessError(_(
            "You are not allowed to modify Bills of Materials. "
            "Please enable BOM Create/ Edit Access on the user master."
        ))


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    produce_delay = fields.Integer(default=0, readonly=True)
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
    can_create_edit_bom = fields.Boolean(
        compute='_compute_can_create_edit_bom',
    )

    def _compute_can_create_edit_bom(self):
        has_access = self.env.user.has_group('harleys_customization.group_bom_create_edit_access')
        for bom in self:
            bom.can_create_edit_bom = has_access

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        result = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type not in ('form', 'list', 'kanban'):
            return result

        has_access = self.env.user.has_group('harleys_customization.group_bom_create_edit_access')
        arch = etree.fromstring(result['arch'])
        if has_access:
            arch.set('create', 'true')
            arch.set('edit', 'true')
            arch.set('delete', 'false')
            arch.set('duplicate', 'true')
            if view_type == 'list':
                arch.set('multi_edit', 'true')
        else:
            arch.set('create', 'false')
            arch.set('edit', 'false')
            arch.set('delete', 'false')
            arch.set('duplicate', 'false')
            if view_type == 'list':
                arch.set('multi_edit', 'false')

        result['arch'] = etree.tostring(arch, encoding='unicode')
        return result

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
        _check_bom_create_edit_access(self.env)
        if isinstance(vals, list):
            for val in vals:
                val['active'] = False
        else:
            vals['active'] = False
        return super(MrpBom, self).create(vals)

    def write(self, vals):
        _check_bom_create_edit_access(self.env)
        return super().write(vals)

    def unlink(self):
        _check_bom_create_edit_access(self.env)
        return super().unlink()

    def make_state_as_sent(self):
        for record in self:
            record.state = 'sent'
            record.active = False


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    @api.model_create_multi
    def create(self, vals_list):
        _check_bom_create_edit_access(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_bom_create_edit_access(self.env)
        return super().write(vals)

    def unlink(self):
        _check_bom_create_edit_access(self.env)
        return super().unlink()


class MrpBomByproduct(models.Model):
    _inherit = 'mrp.bom.byproduct'

    @api.model_create_multi
    def create(self, vals_list):
        _check_bom_create_edit_access(self.env)
        return super().create(vals_list)

    def write(self, vals):
        _check_bom_create_edit_access(self.env)
        return super().write(vals)

    def unlink(self):
        _check_bom_create_edit_access(self.env)
        return super().unlink()
