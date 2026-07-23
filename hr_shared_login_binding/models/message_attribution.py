"""Employee attribution via narrow hooks on mail.thread instead of
per-model create/write overrides (see attribution_targets.py, disabled -
kept for reference/rollback, now superseded twice over by this file).

Two layers, both living on this same mail.thread extension so that both
apply automatically to every chatter-enabled model, present and future,
with no per-model registration:

1. _message_create() override (always on): enriches whatever chatter
   message was already about to be posted - message_post() (manual log
   notes, Discuss, explicit business calls) and
   _message_log()/_message_log_batch() (plain field-tracking messages with
   no matching subtype - this is why "<Record> created" and plain field
   changes need this low-level hook rather than message_post/
   _message_post_after_hook alone, which an earlier version of this file
   used and which only catches the message_post half of the above).

2. create()/write()/unlink() overrides (opt-in per model, see
   attribution_config.py): for models/fields _message_create() can't reach
   at all - untracked fields, and line items whose own chatter isn't shown
   anywhere in the UI. Gated by ir.model flags an admin toggles in Settings
   > Technical > Models, defaulting to off, so a newly installed module's
   models are inert here until someone deliberately opts them in - no code
   change ever required on this module's side.

Why layer 1 is safe to apply unconditionally, unlike a blanket create/write
patch would be:
- It only enriches messages that were already about to be posted; it never
  creates a new message/log entry on its own, so it adds no noise to models
  that don't already log something.
- mail.message does not itself inherit mail.thread, so writing to it here
  cannot recurse back into this hook.
- Outside a web request (cron, RPC, imports) or when nothing resolves to a
  real employee, this is a guaranteed no-op - portal/customer messages and
  system-generated messages are left untouched.

Layer 2 carries more responsibility since it's opt-in, but the same
recursion argument holds (it excludes mail.*/technical models via
attribution_config.py's constraint) and it never posts unless both an
employee is resolved AND an admin has explicitly enabled it for that model.

Because mail.thread is the most widely inherited mixin in the system, a bug
here has broad reach. Every hook is therefore wrapped in its own try/except:
attribution must never be able to break the underlying business action
(confirming a PO, saving a record, deleting a line, etc.) it's attached to.
"""
import logging

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = 'mail.message'

    employee_id = fields.Many2one(
        'hr.employee',
        string="Acting Employee",
        index=True,
        help="Employee who actually performed this action, resolved from "
             "the verified session identity at the time this message was "
             "posted. Set automatically - not meant to be edited by hand.",
    )


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_create(self, values_list):
        messages = super()._message_create(values_list)
        try:
            self._apply_employee_attribution(messages)
        except Exception:
            _logger.exception(
                "Employee attribution failed for message(s) %s on %s; "
                "continuing without it.", messages.ids, self._name,
            )
        return messages

    def _apply_employee_attribution(self, messages):
        if not messages:
            return
        employee = self._get_attribution_employee()
        if not employee:
            return
        note_text = _("Logged by %(employee)s.", employee=employee.name)
        messages = messages.sudo()
        messages.employee_id = employee.id
        for message in messages:
            message.body = self._attribution_inline_note(message.body, note_text)

    def _attribution_inline_note(self, body, note_text):
        """Append note_text as an inline continuation of the message, right
        before the closing tag of its last paragraph, instead of a new block
        below it - keeps chatter entries compact when there are many of
        them (e.g. one per line-item edit). Falls back to a plain append
        for bodies that don't end in a plain "</p>" (rare - e.g. bodies
        with embedded images/tables), which is still correct, just not as
        tightly inline.
        """
        body = Markup(body or '')
        inline = Markup(' <span class="text-muted small">— %s</span>') % note_text
        stripped = body.rstrip()
        if stripped.endswith('</p>'):
            return Markup(stripped[:-len('</p>')]) + inline + Markup('</p>')
        return body + inline

    def _get_attribution_employee(self):
        """Resolve the employee actually behind the current session.

        Returns the employee bound during hr_shared_login_binding's
        employee-verify login step when present, otherwise the individual
        account's own linked employee. Returns an empty recordset outside a
        web request (cron, RPC, imports) or when nothing resolves.
        """
        if not request:
            return self.env['hr.employee']
        employee_id = request.session.get('employee_binding_id')
        if employee_id:
            return self.env['hr.employee'].sudo().browse(employee_id).exists()
        return self.env.user.employee_id

    # ------------------------------------------------------------------
    # Layer 2: opt-in explicit create/write/delete logging (see
    # attribution_config.py for the ir.model flags this reads).
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            self._log_attribution_change(records, _("Created"))
        except Exception:
            _logger.exception(
                "Employee attribution (create) failed on %s; continuing "
                "without it.", self._name,
            )
        return records

    def write(self, vals):
        result = super().write(vals)
        try:
            self._log_attribution_change(self, _("Updated"))
        except Exception:
            _logger.exception(
                "Employee attribution (write) failed on %s%s; continuing "
                "without it.", self._name, self.ids,
            )
        return result

    def unlink(self):
        try:
            self._log_attribution_deletion()
        except Exception:
            _logger.exception(
                "Employee attribution (unlink) failed on %s%s; continuing "
                "without it.", self._name, self.ids,
            )
        return super().unlink()

    def _attribution_record_label(self, record):
        """A human-readable label for a log message that's never falsy.

        display_name is often empty for line items created without their
        free-text description filled in (e.g. from a template) - falling
        back to the record's id avoids ever printing the literal word
        "False" into a chatter note.
        """
        return record.display_name or _("record #%s", record.id)

    def _log_attribution_change(self, records, action):
        if not records:
            return
        log_changes, _log_deletions, parent_field = \
            self.env['ir.model']._get_employee_attribution_flags(self._name)
        if not log_changes:
            return
        employee = self._get_attribution_employee()
        if not employee:
            return
        for record in records:
            target = record[parent_field] if parent_field else record
            if not target:
                continue
            # No need to name the employee here - the _message_create hook
            # above tags every message, including this one, automatically.
            target.message_post(body=_(
                "%(action)s: %(record)s.", action=action,
                record=self._attribution_record_label(record),
            ))

    def _log_attribution_deletion(self):
        if not self:
            return
        _log_changes, log_deletions, parent_field = \
            self.env['ir.model']._get_employee_attribution_flags(self._name)
        if not log_deletions:
            return
        employee = self._get_attribution_employee()
        if not employee:
            return
        if not parent_field:
            # Enforced by attribution_config.py's constraint at config time,
            # but stay defensive: a record's own messages are wiped by
            # mail.thread.unlink() right after this, so posting on self
            # would never be seen.
            _logger.warning(
                "Employee attribution: deletion logging enabled for %s but "
                "no parent field configured; nothing to log to.", self._name,
            )
            return
        for record in self:
            parent = record[parent_field]
            if not parent:
                continue
            parent.message_post(body=_(
                "Deleted: %(record)s.", record=self._attribution_record_label(record),
            ))
