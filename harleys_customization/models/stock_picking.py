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

    @api.model
    def get_action_picking_tree_internal(self):
        action = super().get_action_picking_tree_internal()
        allowed_location_ids = self.env['stock.location']._get_user_allowed_location_ids().ids
        domain = safe_eval(action.get('domain') or '[]')
        action['domain'] = domain + [('location_id', 'in', allowed_location_ids)]
        return action

    def _get_qty_mismatch_moves(self):
        self.ensure_one()
        if self.picking_type_code not in ('internal', 'incoming'):
            return self.env['stock.move']
        return self.move_ids.filtered(
            lambda m: m.state not in ('done', 'cancel')
            and m.product_uom.compare(m.quantity, m.product_uom_qty) != 0
        )

    def button_validate(self):
        self = self.filtered(lambda p: p.state != 'done')

        if len(self) == 1 and not self.env.context.get('skip_qty_mismatch_confirm'):
            mismatch_moves = self._get_qty_mismatch_moves()
            if mismatch_moves:
                wizard = self.env['stock.picking.qty.mismatch.confirm'].create({
                    'picking_id': self.id,
                    'mismatch_move_ids': [(6, 0, mismatch_moves.ids)],
                })
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Quantity Mismatch'),
                    'res_model': 'stock.picking.qty.mismatch.confirm',
                    'res_id': wizard.id,
                    'view_mode': 'form',
                    'target': 'new',
                }

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

        # The second leg must reflect what was actually dispatched, including
        # the selected batches.  Do this only once the first leg is done: the
        # batches are then physically available in transit for the second leg.
        self.filtered(lambda picking: picking.state == 'done')._sync_indent_downstream_batches()
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

    def _get_indent_request(self):
        """The indent.request that generated this picking, if any.

        Both legs of an indent's Dispatch/Transit/Receipt pair are created
        with origin = the indent number (see make_internal_transfer_draft),
        so this is an exact, unambiguous match - it can never pick up a
        sale/MO/PO/replenishment picking, whose origin is never an indent
        number.
        """
        self.ensure_one()
        if self.picking_type_code != 'internal' or not self.origin:
            return self.env['indent.request']
        return self.env['indent.request'].sudo().search([('name', '=', self.origin)], limit=1)

    def _get_indent_transit_sibling(self):
        self.ensure_one()
        if not self._get_indent_request():
            return self.env['stock.picking']
        return self.sudo().search([
            ('id', '!=', self.id),
            ('origin', '=', self.origin),
            ('picking_type_code', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _sync_indent_downstream_batches(self):
        """Copy completed dispatch batch quantities to the indent receipt leg.

        Demand remains the original request.  The receipt move's Trans Qty is
        computed from its move lines, so synchronising those lines is the only
        reliable way to show the dispatched quantity on the sibling picking.
        """
        MoveLine = self.env['stock.move.line'].sudo()
        for picking in self:
            indent = picking._get_indent_request()
            if not indent or picking.picking_type_id != indent.picking_type_id:
                continue

            sibling = picking._get_indent_transit_sibling()
            if not sibling or sibling.state in ('done', 'cancel'):
                continue

            for source_move in picking.move_ids.filtered(
                lambda move: move.state == 'done' and move.move_dest_ids
            ):
                destination_move = source_move.move_dest_ids.filtered(
                    lambda move: move.picking_id == sibling and move.state not in ('done', 'cancel')
                )[:1]
                if not destination_move:
                    continue

                # A source lot can be represented by more than one operation
                # line.  Consolidate it before applying it to the receipt move.
                quantities_by_lot = {}
                for line in source_move.move_line_ids.filtered(
                    lambda line: line.lot_id and not line.product_uom_id.is_zero(line.quantity)
                ):
                    quantities_by_lot[line.lot_id.id] = (
                        quantities_by_lot.get(line.lot_id.id, 0.0) + line.quantity
                    )

                if not quantities_by_lot:
                    continue

                # The dispatch is the source of truth.  Reset existing batch
                # quantities first, including any values entered on the receipt
                # leg before the dispatch was validated.
                destination_move.move_line_ids.filtered(
                    lambda line: line.lot_id
                ).with_context(skip_indent_transit_batch_sync=True).write({'quantity': 0})

                destination_lines_by_lot = {
                    line.lot_id.id: line
                    for line in destination_move.move_line_ids.filtered(lambda line: line.lot_id)
                }
                for lot_id, quantity in quantities_by_lot.items():
                    destination_line = destination_lines_by_lot.get(lot_id)
                    if destination_line:
                        destination_line.with_context(skip_indent_transit_batch_sync=True).write({
                            'quantity': quantity,
                        })
                    else:
                        MoveLine.with_context(skip_indent_transit_batch_sync=True).create({
                            'move_id': destination_move.id,
                            'picking_id': sibling.id,
                            'product_id': destination_move.product_id.id,
                            'product_uom_id': destination_move.product_uom.id,
                            'lot_id': lot_id,
                            'location_id': destination_move.location_id.id,
                            'location_dest_id': destination_move.location_dest_id.id,
                            'company_id': sibling.company_id.id,
                            'quantity': quantity,
                        })


class StockMove(models.Model):
    _inherit = 'stock.move'


    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        vals = super(StockMove, self)._prepare_move_line_vals(quantity, reserved_quant)
        # Override quantity to 0 for GRN
        if self.picking_code == 'incoming':
            vals['quantity'] = 0
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        if not self.env.context.get('skip_indent_transit_sync'):
            moves._sync_indent_transit_add()
        return moves

    def write(self, vals):
        result = super().write(vals)
        if 'product_uom_qty' in vals and not self.env.context.get('skip_indent_transit_sync'):
            for move in self:
                paired = move.move_dest_ids or move.move_orig_ids
                if (
                    paired
                    and paired.state not in ('done', 'cancel')
                    and paired.product_uom_qty != vals['product_uom_qty']
                ):
                    paired.with_context(skip_indent_transit_sync=True).write({
                        'product_uom_qty': vals['product_uom_qty'],
                    })
        return result

    def _sync_indent_transit_add(self):
        """Mirror a line manually added on one leg of an indent's chained
        transfer (Dispatch <-> Receipt) onto the other leg, so both legs
        keep representing the same shipment. Only ever touches pickings
        whose origin matches an indent.request - see _get_indent_request.
        """
        for move in self:
            if move.move_dest_ids or move.move_orig_ids:
                continue
            picking = move.picking_id
            if not picking or picking.state in ('done', 'cancel'):
                continue
            indent = picking._get_indent_request()
            if not indent:
                continue
            sibling = picking._get_indent_transit_sibling()
            if not sibling or sibling.state in ('done', 'cancel'):
                continue
            # Capture before adding the mirror: a fresh draft move on the
            # sibling would otherwise drag its computed state back to
            # 'draft' (stock.picking._compute_state treats any draft move
            # as making the whole picking draft), and unlike a line added
            # through the picking form, this move is created directly via
            # the ORM so stock.picking.write()'s own
            # _autoconfirm_picking() never runs for it.
            sibling_already_confirmed = sibling.state not in ('draft',)
            if picking.picking_type_id == indent.picking_type_id:
                is_upstream = True
            elif picking.picking_type_id == indent.via_picking_type_id:
                is_upstream = False
            else:
                continue
            mirror = self.env['stock.move'].sudo().with_context(skip_indent_transit_sync=True).create({
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'product_uom': move.product_uom.id,
                'picking_id': sibling.id,
                'company_id': sibling.company_id.id,
            })
            if is_upstream:
                move.move_dest_ids = [(4, mirror.id)]
            else:
                mirror.move_dest_ids = [(4, move.id)]
            if sibling_already_confirmed:
                mirror._action_confirm()

class StockLot(models.Model):
    _inherit = 'stock.lot'

    def _check_unique_lot(self):
        return

    def action_get_batch_availability(self, location_id):
        self.ensure_one()
        quants = self.env['stock.quant'].search([
            ('lot_id', '=', self.id),
            ('location_id', '=', location_id),
        ])
        return sum(quants.mapped('available_quantity'))

class StockScrap(models.Model):
    _inherit = "stock.scrap"

    scrap_location_id = fields.Many2one(
        string="Inv Adj Location",
    )

    scrap_reason_tag_ids = fields.Many2many(
        string="Inv Adj Reason", required=True
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
        domain=lambda self: [('id', 'in', self.env['stock.location']._get_user_allowed_location_ids().ids)],
        required=True,
        check_company=True,
        default=False
    )

    @api.model
    def action_view_inv_adjustments(self):
        action = self.env["ir.actions.act_window"]._for_xml_id("stock.action_stock_scrap")
        allowed_location_ids = self.env['stock.location']._get_user_allowed_location_ids().ids

        domain = safe_eval(action.get("domain") or "[]")
        context = safe_eval(action.get("context") or "{}")

        action["domain"] = domain + [("location_id", "in", allowed_location_ids)]
        action["context"] = context
        action["context"]["user_allowed_location_ids"] = allowed_location_ids
        return action

    def action_validate_multi(self):
        for scrap in self.filtered(lambda s: s.state != 'done'):
            result = scrap.action_validate()
            if isinstance(result, dict):
                return result
        return {'type': 'ir.actions.act_window_close'}
