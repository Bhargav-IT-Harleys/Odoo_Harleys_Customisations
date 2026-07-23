"""Admin-facing on/off switch for the create/write/delete logging in
message_attribution.py - reuses ir.model (Settings > Technical > Models)
rather than a new screen, since it's already searchable by name/module and
already restricted to technical users.

Two flags, deliberately separate rather than one:
- employee_attribution_log_changes: posts an explicit note on every
  create/write. Meant for models/fields with no field tracking configured
  (e.g. line items) - enabling it on a model whose tracked fields already
  post native messages (enriched automatically by MailThread._message_create
  in message_attribution.py) will show a second, redundant note alongside
  the native one.
- employee_attribution_log_deletions: posts a note when a record is removed.
  Always safe to enable - deletions aren't covered by field tracking at all,
  so there's no equivalent "native" message to duplicate.

employee_attribution_parent_field_id points (via ir.model.fields, so it's a
searchable dropdown of real field labels rather than a technical name typed
blind) to a Many2one field on this model pointing to a parent document
(e.g. "Indent Request" on the Indent Request Line model). When set, notes
are posted on that parent's chatter instead of this model's own - required
for line items (no visible chatter panel of their own in the UI) and
required for deletions to be visible at all (mail.thread.unlink() removes a
record's own messages in the same transaction, so a note posted on the
record being deleted would never survive to be seen).
"""
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError

# Infrastructure the mail/system machinery itself relies on - logging here
# risks recursion (posting a message is itself a write) or noise on models
# that fire on every request. Never selectable, regardless of admin intent.
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
             "tracking at all. Requires 'Attribution Parent Field' below, "
             "since a deleted record's own messages are removed by Odoo "
             "immediately afterwards and would never be seen otherwise.")
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
            if rec.model not in self.env.registry.models or not hasattr(self.env[rec.model], 'message_post'):
                raise ValidationError(_(
                    "Model '%s' has no chatter (mail.thread) to log "
                    "employee attribution to.", rec.model))
            parent_field = rec.employee_attribution_parent_field_id
            if parent_field and (parent_field.model_id.id != rec.id or parent_field.ttype != 'many2one'):
                raise ValidationError(_(
                    "'%(field)s' is not a Many2one field on model "
                    "'%(model)s'.", field=parent_field.name, model=rec.model))
            if rec.employee_attribution_log_deletions and not parent_field:
                raise ValidationError(_(
                    "'Log Deletions' requires 'Attribution Parent Field' to "
                    "be set on '%s' - otherwise there is nowhere for the "
                    "note to survive being posted.", rec.model))

    @tools.ormcache('model_name')
    def _get_employee_attribution_flags(self, model_name):
        """Returns (log_changes, log_deletions, parent_field_name_or_False)
        for a model, cached since this is read on every create/write/unlink
        of every attribution-enabled model. Invalidated in write() below.
        """
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
