"""Admin config for message_attribution.py's opt-in logging - reuses
ir.model (Settings > Technical > Models). See
employee-attribution-current-state.md for the full design writeup.
"""
import logging

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Logging here risks recursion or noise in the mail/system internals -
# never selectable, regardless of admin intent.
_ATTRIBUTION_EXCLUDED_PREFIXES = (
    'mail.', 'bus.', 'ir.', 'base_automation', 'iap.', 'studio.', 'res.users',
)


class IrModel(models.Model):
    _inherit = 'ir.model'

    employee_attribution_log_changes = fields.Boolean(
        string="Log Every Change (Employee)",
        help="Post an explicit 'Created/Updated' note on every create/write "
             "for this model, regardless of field tracking. Meant for "
             "models/fields with no tracking configured (e.g. line items) - "
             "enabling it on a model that already has tracking=True fields "
             "will show a duplicate note alongside the native tracking "
             "message.")
    employee_attribution_log_deletions = fields.Boolean(
        string="Log Deletions (Employee)",
        help="Post a 'Deleted' note when a record of this model is removed. "
             "Always safe to enable - deletions aren't covered by field "
             "tracking at all. Posted on 'Attribution Parent Field' below "
             "if set (visible immediately in that document's chatter); "
             "otherwise recorded in the standalone Employee Attribution "
             "Log instead, since a deleted record's own messages are "
             "removed by Odoo immediately afterwards.")
    employee_attribution_parent_field_id = fields.Many2one(
        'ir.model.fields',
        string="Attribution Parent Field",
        domain="[('model_id', '=', id), ('ttype', '=', 'many2one')]",
        help="The Many2one field on this model pointing to its parent "
             "document (e.g. 'Indent Request' on the Indent Request Line "
             "model). When set, create/write/delete notes are posted on "
             "that parent's chatter instead of this model's own.")

    @api.constrains('employee_attribution_log_changes',
                     'employee_attribution_log_deletions',
                     'employee_attribution_parent_field_id', 'model')
    def _check_employee_attribution_config(self):
        for rec in self:
            if not (rec.employee_attribution_log_changes or rec.employee_attribution_log_deletions):
                continue
            if rec.model.startswith(_ATTRIBUTION_EXCLUDED_PREFIXES):
                raise ValidationError(_(
                    "Employee attribution cannot be enabled on technical/"
                    "infrastructure model '%s'.", rec.model))
            if not rec._is_employee_attribution_eligible():
                raise ValidationError(_(
                    "Model '%s' has no chatter (mail.thread) to log "
                    "employee attribution to.", rec.model))
            parent_field = rec.employee_attribution_parent_field_id
            if parent_field and (parent_field.model_id.id != rec.id or parent_field.ttype != 'many2one'):
                raise ValidationError(_(
                    "'%(field)s' is not a Many2one field on model "
                    "'%(model)s'.", field=parent_field.name, model=rec.model))

    @tools.ormcache('model_name')
    def _get_employee_attribution_flags(self, model_name):
        # Cached: read on every create/write/unlink of every model with
        # attribution enabled. Invalidated in write() below.
        rec = self.sudo().search([('model', '=', model_name)], limit=1)
        return (
            rec.employee_attribution_log_changes,
            rec.employee_attribution_log_deletions,
            rec.employee_attribution_parent_field_id.name or False,
        )

    def write(self, vals):
        result = super().write(vals)
        if {'employee_attribution_log_changes', 'employee_attribution_log_deletions',
                'employee_attribution_parent_field_id'} & set(vals):
            self.env.registry.clear_cache()
        return result

    def _is_employee_attribution_eligible(self):
        self.ensure_one()
        return (
            not self.model.startswith(_ATTRIBUTION_EXCLUDED_PREFIXES)
            and self.model in self.env.registry.models
            and hasattr(self.env[self.model], 'message_post')
        )

    def _auto_detect_attribution_parent_field(self):
        # ondelete='cascade' is the standard Odoo convention for a line
        # item's Many2one to its parent document. Only trust a single
        # candidate - ambiguous or none at all is left for manual review.
        self.ensure_one()
        candidates = self.field_id.filtered(
            lambda f: f.ttype == 'many2one' and f.on_delete == 'cascade')
        return candidates if len(candidates) == 1 else self.env['ir.model.fields']

    def action_enable_employee_attribution(self):
        skipped = []
        for rec in self:
            if not rec._is_employee_attribution_eligible():
                skipped.append(rec.model)
                continue
            vals = {
                'employee_attribution_log_changes': True,
                'employee_attribution_log_deletions': True,
            }
            if not rec.employee_attribution_parent_field_id:
                auto_field = rec._auto_detect_attribution_parent_field()
                if auto_field:
                    vals['employee_attribution_parent_field_id'] = auto_field.id
            rec.write(vals)
        if skipped:
            _logger.info(
                "Employee attribution bulk-enable: skipped %d incompatible "
                "model(s): %s", len(skipped), skipped,
            )
