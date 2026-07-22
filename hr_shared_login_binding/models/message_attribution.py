"""Employee attribution via a single, narrow hook on mail.thread instead of
per-model create/write overrides (see attribution_targets.py, currently
disabled - kept for reference/rollback).

Rather than listing every model that should log attribution, this extends
mail.thread's low-level _message_create(). That method is the one place
every message-posting path converges before a mail.message row is actually
written - message_post() (manual log notes, Discuss, explicit business
calls) and _message_log()/_message_log_batch() (plain field-tracking
messages with no matching subtype, e.g. a tracked field changing with no
custom subtype defined - this is why "<Record> created" and plain field
changes need the low-level hook: they go through _message_log, not
message_post, and would be missed by hooking message_post/
_message_post_after_hook alone, as an earlier version of this file did).
Because every chatter-enabled model composes mail.thread (directly or via a
variant like mail.thread.cc / mail.thread.main.attachment), this applies
automatically to all of them - present and future - with no per-model
registration and no manifest dependency on their owning modules.

Why this is safe to apply unconditionally, unlike a blanket create/write
patch:
- It only enriches messages that were already about to be posted; it never
  creates a new message/log entry on its own, so it adds no noise to models
  that don't already log something.
- mail.message does not itself inherit mail.thread, so writing to it here
  cannot recurse back into this hook.
- Outside a web request (cron, RPC, imports) or when nothing resolves to a
  real employee, this is a guaranteed no-op - portal/customer messages and
  system-generated messages are left untouched.

Because mail.thread is the most widely inherited mixin in the system, a bug
here has broad reach. _apply_employee_attribution() is therefore wrapped in
its own try/except: attribution must never be able to break the underlying
business action (confirming a PO, saving a record, etc.) it's attached to.
"""
import logging

from markupsafe import Markup

from odoo import fields, models, _
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
        note = Markup('<div class="text-muted small" style="margin-top:2px">%s</div>') % _(
            "Logged by %(employee)s.", employee=employee.name,
        )
        messages = messages.sudo()
        messages.employee_id = employee.id
        for message in messages:
            message.body = Markup(message.body or '') + note

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
