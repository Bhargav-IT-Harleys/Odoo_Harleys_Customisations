"""Folds the acting employee into core's own "Done By" (create_uid) column
on the stock.move.line History list (stock.view_move_line_tree, opened via
stock.quant's History button) - reachable and visible where Inventory
Adjustments actually shows who did something, unlike stock.quant itself
(list-only action, no form/chatter ever shown - see
employee-attribution-current-state.md for why that path was dropped).

employee_id is set once at create(), same as create_uid itself: this is
"who did the move," not "who last touched the record" - it shouldn't
change if the record is later validated/modified by someone else.
"""
from odoo import api, fields, models
from odoo.http import request


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    employee_id = fields.Many2one(
        'hr.employee', string="Employee", readonly=True, copy=False,
        help="Employee behind the session that created this move line - "
             "resolved the same way as the rest of hr_shared_login_binding's "
             "attribution (bound employee for a shared login, or the "
             "individual account's own linked employee otherwise).")
    done_by_display = fields.Char(string="Done By", compute='_compute_done_by_display')

    @api.depends('create_uid.name', 'employee_id.name')
    def _compute_done_by_display(self):
        for line in self:
            if line.employee_id:
                # sudo(): this field only ever displays a name for attribution - it must not
                # require the viewer to have HR access to an employee in another company.
                line.done_by_display = f"{line.create_uid.name} ({line.employee_id.sudo().name})"
            else:
                line.done_by_display = line.create_uid.name or ''

    def _get_attribution_employee(self):
        if not request:
            return self.env['hr.employee']
        employee_id = request.session.get('employee_binding_id')
        if employee_id:
            return self.env['hr.employee'].sudo().browse(employee_id).exists()
        return self.env.user.employee_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        employee = records._get_attribution_employee()
        if employee:
            records.employee_id = employee.id
        return records
