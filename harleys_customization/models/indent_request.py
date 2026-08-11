from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta

_STATES = [
    ("draft", "Draft"),
    ("sent", "Sent"),
    ("locked", "Approved"),
    ("closed", "Closed")
]

class IndentRequest(models.Model):
    _name = 'indent.request'
    _description = 'Indent Request'
    _company_id_field = 'company_id'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)
    
    @api.model
    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)
    
    def _get_records(self):
        return self.search([('company_id', '=', self.env.user.company_id.id)])

    
    @api.model
    def _get_default_name(self):
        return self.env["ir.sequence"].next_by_code("indent.request")

    name = fields.Char(
        string="Indent Number",
        required=True,
        default=lambda self: _("New"),
        tracking=True,
    )

    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)
    indent_date = fields.Date(
        string='Date',
        default=lambda self: fields.Date.context_today(self)
    )
    delivery_from = fields.Many2one(
        'stock.warehouse',
        string='Delivery From',
        required=True
    )

    via_location_id = fields.Many2one('stock.location', string="Delivery Via", required=True, store=True)

    # "Random Test"
    delivery_to = fields.Many2one(
        'stock.warehouse',
        string='Delivery To',
        required=True
    )

    picking_type_id = fields.Many2one('stock.picking.type', string="Operation Type")
    via_picking_type_id = fields.Many2one('stock.picking.type', string="Via Operation Type")

    requested_by = fields.Many2one(
        comodel_name="res.users",
        required=True,
        copy=False,
        tracking=True,
        default=_get_default_requested_by,
        index=True,
    )

    indent_template = fields.Many2one(
        'indent.request.templates',
        string='Indent Template',
        required=True
    )

    # received_date = fields.Date(
    #     string='Receiving Date',
    #     default=lambda self: fields.Date.context_today(self) + timedelta(days=2),
    # )
    received_date = fields.Date(string='Receiving Date',required=True)

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=lambda self: self.env.company,
        tracking=True,
    )
    
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        store=True,
        copy=False,
        default="draft",
    )

    line_count = fields.Integer(
        string="Purchase Request Line count",
        compute="_compute_line_count",
        readonly=True,
    )

    line_ids = fields.One2many(
        comodel_name="indent.request.line",
        inverse_name="request_id",
        string="Products to Manufacturing",
        readonly=False,
        copy=True,
        tracking=True,
    )

    employee_id = fields.Many2one('hr.employee', string="Requested Employee", copy=False)
    password = fields.Char(string="Enter Password")
    is_valid = fields.Boolean("Is Valid", readonly=True)


    internal_transfer_count = fields.Integer(
        string="Internal Transfer Count",
        compute="_compute_internal_transfer_count"
    )


    def _can_be_deleted(self):
        self.ensure_one()
        return self.state == "draft"

    def unlink(self):
        for request in self:
            if not request._can_be_deleted():
                raise UserError(
                    _("You cannot delete a indent request which is not draft.")
                )
        return super().unlink()

    def _compute_internal_transfer_count(self):
        for rec in self:
            # rec.internal_transfer_count = self.env['stock.picking'].search_count([
            #     ('origin', '=', rec.name),
            #     ('picking_type_code', '=', 'internal')
            # ])
            transfer = self.env['stock.picking'].search([
                ('origin', '=', rec.name),
                ('picking_type_code', '=', 'internal')
            ])
            transit_transfer = self.env['stock.picking'].search([
                ('origin', 'in', [trans.name for trans in transfer]),
                ('picking_type_code', '=', 'internal')
            ])
            transfer_ids = [trans.id for trans in transfer] + [transit_trans.id for transit_trans in transit_transfer]
            rec.internal_transfer_count = self.env['stock.picking'].search_count([('id', 'in', transfer_ids)])

    manufacturing_order_count = fields.Integer(
        string="Manufacturing Order Count",
        compute="_compute_manufacturing_order_count"
    )

    internal_transfer_status = fields.Char(
        string="Internal Transfer Status",
        compute="_compute_internal_transfer_status",
        readonly=True,
    )
    manufacturing_order_status = fields.Char(
        string="Manufacturing Orders",
        compute="_compute_manufacturing_order_status",
        readonly=True,
    )

    @api.depends("name")
    def _compute_manufacturing_order_status(self):
        state_labels = dict(
            self.env["mrp.production"]._fields["state"].selection
        )

        for rec in self:
            mos = self.env["mrp.production"].search([
                ("origin", "ilike", rec.name),
                ("company_id", "=", rec.company_id.id),
            ])

            values = []
            for mo in mos:
                state_name = state_labels.get(mo.state, mo.state)
                values.append(f"{mo.name} - {state_name}")

            rec.manufacturing_order_status = ", ".join(values)

    def _compute_internal_transfer_status(self):
        state_labels = dict(
            self.env["stock.picking"]._fields["state"].selection
        )

        for rec in self:
            pickings = self.env["stock.picking"].sudo().search([
                ("origin", "=", rec.name),
                ("picking_type_code", "=", "internal"),
                ("company_id", "=", rec.company_id.id),
            ])
            transit_pickings = self.env["stock.picking"].sudo().search([
                ("origin", "in", [trans.name for trans in pickings]),
                ("picking_type_code", "=", "internal"),
                ("company_id", "=", rec.company_id.id),
            ])
            trans_picking = pickings + transit_pickings
            rec.internal_transfer_status = ", ".join(
                f"{p.name} - {state_labels.get(p.state, p.state)}"
                for p in trans_picking
            )


    def _compute_manufacturing_order_count(self):
        for rec in self:
            rec.manufacturing_order_count = self.env['mrp.production'].search_count([
                ('origin', 'ilike', rec.name),
            ])

    # @api.constrains('indent_template', 'employee_id', 'password')
    # def _check_template_credentials(self):
    #     for rec in self:
    #         if rec.indent_template:

    #             # Check employee
    #             if rec.employee_id not in rec.indent_template.employee_ids:
    #                 raise UserError("Provided employee/password is wrong.")

    #             # Check password
    #             if rec.password != rec.indent_template.password:
    #                 raise UserError("Provided employee/password is wrong.")
    @api.constrains('indent_template', 'password')
    def _check_template_password(self):
        for rec in self:
            if bool(rec.indent_template) != bool(rec.password):
                raise UserError("Invalid password for the selected outlet.")
            else:
                rec.is_valid = True

            if rec.indent_template and rec.password:
                if rec.password != rec.indent_template.password:
                    raise UserError("Invalid password for the selected outlet.")
                else:
                    rec.is_valid = True

    def action_verify_template(self):
        """Verify template and password, then set is_valid flag to show products section"""
        self.ensure_one()
        self._check_template_password()
        return True

    def action_get_internal_transfers(self):
        self.ensure_one()
        transfers = self.env['stock.picking'].search([
            ('origin', '=', self.name),
            ('picking_type_code', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ])
        transfer_names = [trans.name for trans in transfers] + [self.name]
        if transfers:
            return {
                'type': 'ir.actions.act_window',
                'name': _("Internal Transfers"),
                'res_model': 'stock.picking',
                'view_mode': 'list,form',
                'domain': [
                    ('origin', 'in', transfer_names),
                    ('picking_type_code', '=', 'internal'),
                    ('company_id', '=', self.env.company.id),
                ],
                'context': {'default_origin': transfer_names},
                'target': 'current',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}

    def action_get_manufacturing_order(self):
        self.ensure_one()
        mo = self.env['mrp.production'].search([
            ('origin', 'ilike', self.name),
            ('company_id', '=', self.env.company.id),
        ])

        if mo:
            return {
                'type': 'ir.actions.act_window',
                'name': _("Manufacturing Orders"),
                'res_model': 'mrp.production',
                'view_mode': 'list,form',
                'domain': [
                    ('origin', 'ilike', self.name),
                    ('company_id', '=', self.env.company.id),
                ],
                'context': {'default_origin': self.name},
                'target': 'current',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}
    
    def action_sent(self):
        self._check_template_password()
        warning = self._validate_zero_demand_lines()

        if warning:
            return warning
        return self._action_sent_internal()

    def _action_sent_internal(self):
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)

        for request in self:
            if not request.line_ids:
                raise UserError(_("No Indent Request Line"))

            for line in request.line_ids:
                if (
                    manufacture_route
                    and manufacture_route in line.product_id.route_ids
                    and not request._product_has_bom(line.product_id)
                ):
                    raise UserError(_(
                        "For the '%s' BOM missing contact your city head"
                    ) % line.product_id.display_name)

            if request.state == 'draft':
                request.state = 'sent'
            if request.line_ids:
                request.line_ids.write({'state': 'sent'})

    def action_close(self):
        self.ensure_one()

        wizard = self.env["indent.close.confirm"].create({
            "request_id": self.id,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Confirm Close"),
            "res_model": "indent.close.confirm",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
    
    def _action_close_internal(self):
        self.ensure_one()

        self._check_template_password()

        if self.state == "locked":
            self.state = "closed"

        self.line_ids.write({
            "state": "closed",
        })

    @api.depends("line_ids")
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.mapped("line_ids"))

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        default.update({"state": "draft", "name": self._get_default_name()})
        return super().copy(default)
    
    def state_checker(self):
        for record in self:
            if record.line_ids:
                if not [line for line in record.line_ids if line.state != 'locked']:
                    record.state = 'locked'

    @api.model
    def _cron_close_requests_by_received_qty(self):
        requests = self.sudo().search([
            ('state', '=', 'locked'),
            ('line_ids', '!=', False),
        ])
        requests.filtered(
            lambda request: all(
                line.received_qty >= line.product_qty
                for line in request.line_ids
            )
        ).write({'state': 'closed'})
        return True

    @api.depends("state")
    def _compute_is_editable(self):
        for rec in self:
            if rec.state in ("close"):
                rec.is_editable = False
            else:
                rec.is_editable = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self._get_default_name()
            if not vals.get('company_id'):
                vals['company_id'] = self.env.company.id
        requests = super().create(vals_list)
        return requests

    @api.onchange("indent_template")
    def _onchange_indent_template(self):
        if self.indent_template:
            self.delivery_from = self.indent_template.delivery_from
            self.delivery_to = self.indent_template.delivery_to

            self.via_location_id = self.indent_template.via_location_id

            self.picking_type_id = self.indent_template.picking_type_id
            self.via_picking_type_id = self.indent_template.via_picking_type_id

            self.line_ids = False
            for template_line in self.indent_template.line_ids:
                self.line_ids = [(0, 0, {
                    "product_id" : template_line.product_id.id,
                    "name" : template_line.name,
                    "default_code" : template_line.default_code,
                    "hsn_code" : template_line.hsn_code,
                    "product_uom_id" : template_line.product_uom_id.id, 
                    "product_qty" : template_line.product_qty, 
                    "comments" : template_line.comments,
                })]


    def _product_has_bom(self, product, company=None):
        company = company or self.company_id
        return bool(self.env['mrp.bom'].search([
            '|',
            ('product_id', '=', product.id),
            '&',
            ('product_id', '=', False),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('company_id', 'in', [company.id, False]),
            ('state', 'in', ['approved']),
        ], limit=1))

    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _("You cannot delete this record in its current state. Only records in Draft state can be deleted.")
                )
        return super().unlink()
    
    def _validate_zero_demand_lines(self):
        self.ensure_one()

        zero_lines = self.line_ids.filtered(
            lambda l: (l.product_qty or 0.0) <= 0
        )

        if not zero_lines:
            return False

        wizard = self.env["indent.zero.qty.warning"].create({
            "request_id": self.id,
            "zero_line_ids": [(6, 0, zero_lines.ids)],
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Zero Demand Quantity"),
            "res_model": "indent.zero.qty.warning",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }


class IndentRequestLine(models.Model):
    _name = 'indent.request.line'
    _description = 'Indent Request Line'
    _company_id_field = 'company_id'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]


    request_id = fields.Many2one(
        comodel_name="indent.request",
        string="Indent Request",
        ondelete="cascade",
        readonly=True,
        index=True,
    )

    name = fields.Char(string="Description", tracking=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        tracking=True,
    )

    categ_id = fields.Many2one(string="Product Category", related='product_id.categ_id', readonly=True)
    
    qty_available = fields.Float(
        string="On Hand QTY",
        compute='_compute_quantities_custom',
        readonly=True,
    )
    batch_size = fields.Float(string="Batch Size", related="product_id.batch_size")
    default_code = fields.Char(string="Internal Reference", related="product_id.default_code")
    hsn_code = fields.Char(string="HSN/SAC Code")
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM"
    )
    product_qty = fields.Float(
        string="Qty", tracking=True, digits="Product Unit"
    )
    received_qty = fields.Float(
        string="Received Qty", digits="Product Unit",
        compute='_compute_qty'
    )

    supplied_qty = fields.Float(
        string="Supplied Qty", digits="Product Unit",
        compute='_compute_supplied_qty'
    )
    comments = fields.Char(string="Comments")

    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
        copy=False,
        default="draft",
    )

    #Invisible Fields
    is_editable = fields.Boolean(compute="_compute_is_editable", readonly=True)

    indent_number = fields.Char(
        string="Indent Number",
        related="request_id.name",
    )

    indent_date = fields.Date(
        string='Date',
        related="request_id.indent_date",
    )

    delivery_from = fields.Many2one(
        'stock.warehouse',
        string='Delivery From',
        related="request_id.delivery_from",
    )

    via_location_id = fields.Many2one('stock.location', string="Delivery Via", required=True, related="request_id.via_location_id")

    delivery_to = fields.Many2one(
        'stock.warehouse',
        string='Delivery To',
        related="request_id.delivery_to",
    )

    received_date = fields.Date(
        string='Receiving Date',
        related="request_id.received_date",
    )

    requested_by = fields.Many2one(
        comodel_name="res.users",
        related="request_id.requested_by",
        string="Requested by",
        store=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        related="request_id.company_id",
        string="Company",
        store=True,
    )

    def _compute_quantities_custom(self):
        for rec in self:
            rec.qty_available = sum([stock_quant.inventory_quantity_auto_apply for stock_quant in 
            self.env['stock.quant'].sudo().search([('product_id', '=', rec.product_id.id), ('location_id', '=', rec.delivery_from.lot_stock_id.id)])])


    def _compute_qty(self):
        for request in self:
            transit_transfer = self.env['stock.move'].search([
                ('picking_id.origin', '=', request.indent_number),
                ('picking_id.picking_type_code', '=', 'internal'),
                ('picking_id.location_dest_id', '=', request.request_id.delivery_to.lot_stock_id.id),
                ('product_id', '=', request.product_id.id),
            ])
            request.received_qty = sum([transit_trans.quantity for transit_trans in transit_transfer if transit_trans.state == 'done'])

    def _compute_supplied_qty(self):
        for request in self:
            transit_transfer = self.env['stock.move'].search([
                ('picking_id.origin', '=', request.indent_number),
                ('picking_id.picking_type_code', '=', 'internal'),
                ('picking_id.location_id', '=', request.request_id.delivery_from.lot_stock_id.id),
                ('product_id', '=', request.product_id.id),
            ])
            request.supplied_qty = sum([transit_trans.quantity for transit_trans in transit_transfer if transit_trans.state == 'done'])

    def _compute_is_editable(self):
        for rec in self:
            if rec.request_id.state in ("open"):
                rec.is_editable = False
            else:
                rec.is_editable = True

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            name = self.product_id.name
            if self.product_id.description_purchase:
                name += "\n" + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_id.id
            self.product_qty = 0
            self.name = name
            self.hsn_code = self.product_id.l10n_in_hsn_code

    @api.depends('product_qty')
    def _compute_forecasted_issue(self):
        for line in self:
            warehouse = line.purchase_lines.order_id.picking_type_id.warehouse_id
            line.forecasted_issue = False
            if line.product_id:
                virtual_available = line.product_id.with_context(warehouse=warehouse.id,
                                                                 ).virtual_available
                if line.request_state == 'draft':
                    virtual_available += line.product_qty
                if virtual_available < 0:
                    line.forecasted_issue = True

    def action_create_mo(self):
        selected_lines = self.browse(self.env.context.get('active_ids', []))


        if not selected_lines:
            raise UserError(_("Please select at least one indent request line."))
        indent_request = self.env['indent.request.line']
        indent_request_lines = indent_request.search([('id', 'in', selected_lines)])
        for request_line in indent_request_lines:
            if request_line.state == 'draft':
                raise UserError(_("Selected indent request line is in draft state."))
            
            if request_line.state == 'locked':
                raise UserError(_("Selected indent request line is in locked state"))
            indent_request_count = indent_request.search_count([('indent_date', '=', request_line.indent_date), ('state', '!=', 'locked')])
            # if indent_request_count != len(selected_lines):
            #     raise UserError(_("Selected lined should be in same date & within the date all the sent records want to select."))

        delivery_from_values = selected_lines.mapped('delivery_from')
        if len(delivery_from_values) > 1:
            raise UserError(_('Selected lines "Delivery From" location is not same'))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Draft MO',
            'res_model': 'indent.request.line.make.manufacturing.order',
            'view_mode': 'form',
            'view_id': self.env.ref('harleys_customization.view_indent_request_line_make_manufacturing_order').id,
            'target': 'new',
            'context': {'active_ids': self.ids},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('request_id') and not vals.get('state'):
                parent = self.env['indent.request'].browse(vals['request_id'])
                vals['state'] = parent.state
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.request_id.state != 'draft':
                raise UserError(
                    _("You cannot delete this line because the parent Indent Request is not in Draft state.")
                )
        return super().unlink()

    @api.constrains('product_id', 'request_id')
    def _check_duplicate_product(self):
        for line in self:
            if not line.product_id or not line.request_id:
                continue

            duplicate = line.request_id.line_ids.filtered(
                lambda l: l.id != line.id and l.product_id == line.product_id
            )

            if duplicate:
                raise UserError(_(
                    "Product '%s' has already been added to this Indent Request. Duplicate products are not allowed."
                ) % line.product_id.display_name)
