"""Employee attribution on mail.thread. See employee-attribution-current-state.md
and docs/developer-guide.html (HarleysTest repo) for the full design writeup.
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
        help="Employee behind the session that posted this message. Set "
             "automatically - not meant to be edited by hand.",
    )


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_create(self, values_list):
        # Hooking here (not message_post/_message_post_after_hook) because
        # this is the one method both message_post() and the plain
        # tracking-message path (_message_log_batch) both call.
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
        # Splice inside the last </p> so the note reads as a continuation
        # of the message instead of a new block with its own spacing.
        body = Markup(body or '')
        inline = Markup(' <span class="text-muted small">— %s</span>') % note_text
        stripped = body.rstrip()
        if stripped.endswith('</p>'):
            return Markup(stripped[:-len('</p>')]) + inline + Markup('</p>')
        return body + inline

    def _get_attribution_employee(self):
        if not request:
            return self.env['hr.employee']
        employee_id = request.session.get('employee_binding_id')
        if employee_id:
            return self.env['hr.employee'].sudo().browse(employee_id).exists()
        return self.env.user.employee_id

    # Opt-in per model - see attribution_config.py.

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        try:
            _log_changes, _log_deletions, parent_field = \
                self.env['ir.model']._get_employee_attribution_flags(self._name)
            if parent_field:
                self._log_attribution_change(records, _("Created"))
        except Exception:
            _logger.exception(
                "Employee attribution (create) failed on %s; continuing "
                "without it.", self._name,
            )
        return records

    def write(self, vals):
        watched_fields = [
            f for f in ('active', 'state')
            if f in self._fields and f in vals and not getattr(self._fields[f], 'tracking', False)
        ]
        other_fields = any(
            self._fields[f].type not in ('one2many', 'many2many')
            for f in vals
            if f in self._fields and f not in ('active', 'state')
        )
        old_values = (
            {record.id: {f: record[f] for f in watched_fields} for record in self}
            if watched_fields else None
        )
        result = super().write(vals)
        if old_values:
            try:
                self._log_attribution_status_change(watched_fields, old_values)
            except Exception:
                _logger.exception(
                    "Employee attribution (write) failed on %s%s; continuing "
                    "without it.", self._name, self.ids,
                )
        if other_fields:
            try:
                self._register_attribution_update()
            except Exception:
                _logger.exception(
                    "Employee attribution (write) failed on %s%s; continuing "
                    "without it.", self._name, self.ids,
                )
        return result

    def _register_attribution_update(self):
        key = f'hr_shared_login_binding.attribution_update.{self._name}'
        pending = self.env.cr.precommit.data.get(key)
        if pending is None:
            self.env.cr.precommit.data[key] = self
            self.env.cr.precommit.add(self._flush_attribution_updates)
        else:
            self.env.cr.precommit.data[key] = pending | self

    def _flush_attribution_updates(self):
        key = f'hr_shared_login_binding.attribution_update.{self._name}'
        records = self.env.cr.precommit.data.pop(key, None)
        if records:
            records._log_attribution_change(records, _("Updated"))

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
        # display_name is often empty for line items (e.g. template-loaded
        # with no description) - fall back rather than ever print "False".
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
        if not parent_field:
            for record in records:
                record.message_post(body=_(
                    "%(action)s: %(record)s.", action=action,
                    record=self._attribution_record_label(record),
                ))
            return
        # Grouped by parent, one note per batch - a template loading 40
        # lines or a status change cascading to all of them arrives here
        # as one call, not 40.
        by_parent = {}
        for record in records:
            parent = record[parent_field]
            if not parent:
                continue
            by_parent.setdefault(parent, self.browse())
            by_parent[parent] |= record
        for parent, recs in by_parent.items():
            if len(recs) == 1:
                body = _("%(action)s: %(record)s.", action=action,
                          record=self._attribution_record_label(recs))
            else:
                body = _("%(action)s: %(count)s line(s).", action=action, count=len(recs))
            parent.message_post(body=body)

    def _log_attribution_status_change(self, watched_fields, old_values):
        log_changes, _log_deletions, parent_field = \
            self.env['ir.model']._get_employee_attribution_flags(self._name)
        if not log_changes:
            return
        employee = self._get_attribution_employee()
        if not employee:
            return
        state_labels = (
            dict(self.fields_get(['state'])['state']['selection'])
            if 'state' in watched_fields else {}
        )
        by_target = {}
        for record in self:
            old = old_values.get(record.id)
            if not old:
                continue
            lines = []
            if 'active' in old and old['active'] != record.active:
                lines.append(_("Unarchived") if record.active else _("Archived"))
            if 'state' in old and old['state'] != record.state:
                lines.append(_(
                    "Status changed from %(old)s to %(new)s",
                    old=state_labels.get(old['state'], old['state']),
                    new=state_labels.get(record.state, record.state),
                ))
            if not lines:
                continue
            if parent_field:
                target = record[parent_field]
                if not target:
                    continue
            else:
                target = record
            by_target.setdefault(target, []).extend(lines)
        for target, lines in by_target.items():
            target.message_post(body=" ".join(f"{line}." for line in lines))

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
        by_parent = {}
        fallback_records = self.browse()
        for record in self:
            parent = record[parent_field] if parent_field else False
            if parent:
                by_parent.setdefault(parent, self.browse())
                by_parent[parent] |= record
            else:
                fallback_records |= record
        for parent, recs in by_parent.items():
            if len(recs) == 1:
                body = _("Deleted: %(record)s.", record=self._attribution_record_label(recs))
            else:
                body = _("Deleted: %(count)s line(s).", count=len(recs))
            parent.message_post(body=body)
        if fallback_records:
            # No parent - a record's own messages are wiped by
            # mail.thread.unlink() right after this, so hr.attribution.log
            # is the only place this can survive.
            self.env['hr.attribution.log'].sudo().create([{
                'employee_id': employee.id,
                'user_id': self.env.user.id,
                'res_model': self._name,
                'res_id': record.id,
                'record_name': self._attribution_record_label(record),
                'action': 'deleted',
            } for record in fallback_records])
