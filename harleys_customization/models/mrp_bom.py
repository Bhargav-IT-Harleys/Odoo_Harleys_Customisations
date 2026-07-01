# -*- coding: utf-8 -*-

from lxml import etree
from markupsafe import Markup

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import AccessError


_STATE = [
    ('draft', 'Draft'),
    ('sent', 'Sent'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]



class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    code = fields.Char(tracking=True)
    active = fields.Boolean(tracking=True)
    type = fields.Selection(tracking=True)
    product_tmpl_id = fields.Many2one(tracking=True)
    product_id = fields.Many2one(tracking=True)
    bom_line_ids = fields.One2many(tracking=True)
    product_qty = fields.Float(tracking=True)
    product_uom_id = fields.Many2one(tracking=True)
    picking_type_id = fields.Many2one(tracking=True)
    company_id = fields.Many2one(tracking=True)
    consumption = fields.Selection(tracking=True)
    ready_to_produce = fields.Selection(tracking=True)
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


class MrpBomLine(models.Model):
    _name = 'mrp.bom.line'
    _inherit = ['mrp.bom.line', 'mail.thread']

    product_id = fields.Many2one(tracking=True)
    product_qty = fields.Float(tracking=True)
    product_uom_id = fields.Many2one(tracking=True)
    sequence = fields.Integer(tracking=True)
    operation_id = fields.Many2one(tracking=True)
    bom_product_template_attribute_value_ids = fields.Many2many(tracking=True)

    def _post_line_tracking_on_bom(self, old_values_by_line):
        if self.env.context.get('tracking_disable') or self.env.context.get('mail_notrack'):
            return

        for line in self:
            old_values = old_values_by_line.get(line.id)
            if not old_values or not line.bom_id:
                continue

            qty_changed = 'product_qty' in old_values and old_values['product_qty'] != line.product_qty
            uom_changed = 'product_uom_id' in old_values and old_values['product_uom_id'] != line.product_uom_id.id
            if not qty_changed and not uom_changed:
                continue

            component_name = line.product_id.display_name or _("Unknown Component")
            old_uom_name = old_values.get('product_uom_name') or ''
            new_uom_name = line.product_uom_id.display_name or ''

            if qty_changed and uom_changed:
                body = Markup("<p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li></ul>") % (
                    _("BoM line quantity and UoM changed."),
                    _("Component: %s", component_name),
                    _("Previous: %(qty)s %(uom)s", qty=old_values['product_qty'], uom=old_uom_name),
                    _("New: %(qty)s %(uom)s", qty=line.product_qty, uom=new_uom_name),
                )
            elif qty_changed:
                body = Markup("<p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li></ul>") % (
                    _("BoM line quantity changed."),
                    _("Component: %s", component_name),
                    _("Previous Quantity: %(qty)s %(uom)s", qty=old_values['product_qty'], uom=new_uom_name),
                    _("New Quantity: %(qty)s %(uom)s", qty=line.product_qty, uom=new_uom_name),
                )
            else:
                body = Markup("<p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li></ul>") % (
                    _("BoM line UoM changed."),
                    _("Component: %s", component_name),
                    _("Previous UoM: %s", old_uom_name),
                    _("New UoM: %s", new_uom_name),
                )

            line.bom_id.message_post(body=body, subtype_xmlid='mail.mt_note')

    def write(self, vals):
        old_values_by_line = {}
        tracked_fields = {'product_qty', 'product_uom_id'} & vals.keys()
        if tracked_fields:
            old_values_by_line = {
                line.id: {
                    field_name: line[field_name].id if field_name == 'product_uom_id' else line[field_name]
                    for field_name in tracked_fields
                } | {'product_uom_name': line.product_uom_id.display_name}
                for line in self
                if line.bom_id
            }

        result = super().write(vals)
        if old_values_by_line:
            self._post_line_tracking_on_bom(old_values_by_line)
        return result
