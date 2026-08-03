from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.exceptions import AccessError
from odoo.tools.safe_eval import safe_eval


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

<<<<<<< Updated upstream
    @api.model
    def action_view_inv_adjustments(self):
        """Open Inv Adjustments (stock.action_stock_scrap) restricted to
        the current user's allowed locations.

        core's action_stock_scrap is a plain ir.actions.act_window, not a
        Python method, so there's no override point to inject a per-user
        domain/context the way stock.quant's action_view_inventory() does
        for Physical Inventory - this method plus the server action/menu
        rewiring in stock_scrap_views.xml recreates that same pattern here,
        reusing the location-level allow-list that already exists
        (_get_allowed_location_ids) rather than a second, warehouse-level
        mechanism alongside it.

        The domain restriction (not just context) matters for the search
        panel added in the view: confirmed against web/models/models.py's
        search_panel_select_range, a select="one" category's value list is
        computed from the CURRENT model's own records filtered by the
        action's domain, not by applying location_id's own field domain to
        the comodel - so without this domain, the panel would list every
        location that has ever had an adjustment, not just allowed ones.
        """
        action = self.env["ir.actions.act_window"]._for_xml_id("stock.action_stock_scrap")
        allowed_location_ids = self._get_allowed_location_ids().ids

        # _for_xml_id() reads the action record's raw stored field values -
        # domain/context come back as unparsed Python-literal strings (or
        # False if unset), not actual list/dict objects (confirmed: dict()
        # on the raw string blew up trying to treat each character as a
        # key-value pair). safe_eval is Odoo's own standard way to turn
        # these stored expressions back into real Python objects.
        domain = safe_eval(action.get("domain") or "[]")
        context = safe_eval(action.get("context") or "{}")

        action["domain"] = domain + [("location_id", "in", allowed_location_ids)]
        action["context"] = context
        action["context"]["user_allowed_location_ids"] = allowed_location_ids
        return action

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
        creates a second, duplicate stock.move rather than erroring. So
        selecting a mix of draft and already-validated rows and clicking
        "Validate All" is safe - the done ones are simply skipped, not
        re-processed.
        """
        for scrap in self.filtered(lambda s: s.state != 'done'):
            result = scrap.action_validate()
            if isinstance(result, dict):
                return result
        return {'type': 'ir.actions.act_window_close'}
=======
class StockQuant(models.Model):
    _inherit = "stock.quant"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
    )
>>>>>>> Stashed changes
