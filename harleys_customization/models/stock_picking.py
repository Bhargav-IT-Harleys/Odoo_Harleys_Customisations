from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # def button_validate(self):
    #     for line in self.move_line_ids:
    #         if not line.expiration_date:
    #             line._compute_expiration_date()
    #     super().button_validate()
        
    def button_validate(self):
        self = self.filtered(lambda p: p.state != 'done')

        transit_picking_ids = self.with_user(SUPERUSER_ID).filtered(
            lambda picking: picking.location_id.usage == 'transit'
        ).ids
        transit_pickings = self.browse(transit_picking_ids)
        normal_pickings = self - transit_pickings

        result = True
        if normal_pickings:
            result = super(StockPicking, normal_pickings).button_validate()
        if transit_pickings:
            try:
                result = super(StockPicking, transit_pickings).button_validate()
            except AccessError:
                result = super(StockPicking, transit_pickings.with_user(SUPERUSER_ID)).button_validate()
        return result

    def action_cancel(self):
        self = self.filtered(lambda p: p.state not in ('done', 'cancel'))
        if not self.env.context.get('skip_internal_transfer_cancel_confirm', False) and len(self) == 1:
            picking = self
            if picking.picking_type_code == 'internal':
                wizard = self.env['stock.picking.close.confirm'].create({
                    'picking_id': picking.id,
                })
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Confirm Transfer Cancellation'),
                    'res_model': 'stock.picking.close.confirm',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'target': 'new',
                }
        return super(StockPicking, self).action_cancel()

    @api.depends('move_ids.state', 'move_ids.date', 'move_type')
    def _compute_scheduled_date(self):
        for picking in self:
            if not picking.id:
                continue
            moves_dates = picking.move_ids.filtered(lambda move: move.state not in ('done', 'cancel')).mapped('date')
            if picking.move_type == 'direct':
                picking.scheduled_date = default=picking.scheduled_date
            else:
                picking.scheduled_date = max(moves_dates, default=picking.scheduled_date or fields.Datetime.now())


    def generate_report(self):        
        report_action = self.env.ref('stock.action_report_delivery')
        return report_action.with_user(SUPERUSER_ID).report_action(self)


class StockMove(models.Model):
    _inherit = 'stock.move'


    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity, reserved_quant)
        # Override quantity to 0 for GRN
        if self.picking_code == 'incoming':
            vals['quantity'] = 0
        return vals

class StockLot(models.Model):
    _inherit = 'stock.lot'

    def _check_unique_lot(self):
        return

class StockScrap(models.Model):
    _inherit = "stock.scrap"

    scrap_location_id = fields.Many2one(
        string="Inv Adj Location",
    )

    scrap_reason_tag_ids = fields.Many2many(
        string="Inv Adj Reason", required=True
    )
    allowed_location_ids = fields.Many2many(
        'stock.location',
        string='Allowed Locations',
        compute='_compute_allowed_location_ids',
    )

    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        required=True,
        states={'done': [('readonly', True)]},
    )

    def _get_allowed_location_ids(self):
        """
        Return stock.location recordset the current user is allowed to use,
        derived from their allowed_warehouse_ids on res.users.
        Falls back to all active internal locations for the company.
        """
        user = self.env.user
        allowed_warehouses = getattr(user, 'allowed_warehouse_ids', self.env['stock.warehouse'])

        if allowed_warehouses:
            warehouse_view_loc_ids = allowed_warehouses.mapped('view_location_id').ids
            return self.env['stock.location'].search([
                ('location_id', 'child_of', warehouse_view_loc_ids),
                ('usage', '=', 'internal'),
                ('active', '=', True),
            ])
        else:
            company_id = self.env.company.id
            return self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('active', '=', True),
                '|',
                ('company_id', '=', False),
                ('company_id', '=', company_id),
            ])
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain=lambda self: [('id', 'in', self._get_allowed_location_ids().ids)],
        required=True,
        states={'done': [('readonly', True)]},
        check_company=True,
        default=False
    )

    def action_validate_multi(self):
        """Validate several draft Inv Adjustment lines in one action.

        Does not change action_validate() itself - just calls the existing,
        single-record method once per record. If a record can't be
        validated (e.g. insufficient quantity), action_validate() returns
        a warning wizard instead of completing; that's surfaced immediately
        and the loop stops there, so nothing after it is silently skipped -
        records already validated earlier in the loop stay validated, and
        re-running this after resolving the warning picks up where it left off.

        Already-done records are skipped rather than re-validated: core's
        action_validate()/do_scrap() has no guard against being called
        twice on the same record, and confirmed by testing, doing so
        creates a second, duplicate stock.move rather than erroring. The
        per-row "Validate" button is already safe (the view hides it once
        state == 'done'), but this header action has no such row-level
        filter if a user selects a mix of draft and already-validated rows.

        The button is display="always" (see the view), so it isn't gated
        on the user having checkbox-selected anything - same reasoning as
        stock.quant's own action_apply_all. That means `self` here may not
        reflect "everything currently on screen", so - matching that same
        core method - re-query the list's own active_domain when one is
        present, falling back to `self` only if it isn't (e.g. called some
        other way than from this exact list).
        """
        records = self
        active_domain = self.env.context.get('active_domain')
        if active_domain is not None:
            records = self.search(active_domain)
        for scrap in records.filtered(lambda s: s.state != 'done'):
            result = scrap.action_validate()
            if isinstance(result, dict):
                return result
        return {'type': 'ir.actions.act_window_close'}
