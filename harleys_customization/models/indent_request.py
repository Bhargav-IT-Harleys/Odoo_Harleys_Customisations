from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date

_STATES = [
    ("draft", "Draft"),
    ("sent", "Sent"),
    ("locked", "Locked")
]

class IndentRequest(models.Model):
    _name = 'indent.request'
    _description = 'Indent Request'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)
    
    @api.model
    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)
    
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
    current_date = fields.Date(
        string='Date',
        default=lambda self: date.today()
    )

    delivery_from = fields.Many2one(
        'stock.warehouse',
        string='Delivery From',
        required=True
    )

    delivery_to = fields.Many2one(
        'stock.warehouse',
        string='Delivery To',
        required=True
    )

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
        string='Outlet Wise Indent Template',
        required=True
    )

    received_date = fields.Date(
        string='Received Date'
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=_company_get,
        tracking=True,
    )
    
    state = fields.Selection(
        selection=_STATES,
        string="Status",
        index=True,
        tracking=True,
        required=True,
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

    def action_sent(self):
        if self.state == 'draft':
            self.state = 'sent'
        if self.line_ids:
            for line in self.line_ids:
                line.state = 'sent'

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
        requests = super().create(vals_list)
        return requests

    @api.onchange("indent_template")
    def _onchange_indent_template(self):
        if self.indent_template:
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


class IndentRequestLine(models.Model):
    _name = 'indent.request.line'
    _description = 'Indent Request Line'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]


    request_id = fields.Many2one(
        comodel_name="indent.request",
        string="Indent Request",
        ondelete="cascade",
        readonly=True,
        index=True,
        auto_join=True,
    )

    name = fields.Char(string="Description", tracking=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        domain=[("purchase_ok", "=", True)],
        tracking=True,
    )
    default_code = fields.Char(string="Internal Reference", related="product_id.default_code")
    hsn_code = fields.Char(string="HSN/SAC Code")
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        related="product_id.uom_id",
        domain="[('category_id', '=', product_uom_category_id)]",
    )
    product_qty = fields.Float(
        string="Qty", tracking=True, digits="Product Unit of Measure"
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

    current_date = fields.Date(
        string='Date',
        related="request_id.current_date",
    )

    delivery_from = fields.Many2one(
        'stock.warehouse',
        string='Delivery From',
        related="request_id.delivery_from",
    )

    delivery_to = fields.Many2one(
        'stock.warehouse',
        string='Delivery To',
        related="request_id.delivery_to",
    )

    received_date = fields.Date(
        string='Received Date',
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
            if self.product_id.code:
                name = f"[{self.product_id.code}] {name}"
            if self.product_id.description_purchase:
                name += "\n" + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_id.id
            self.product_qty = 1
            self.name = name

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
        
        indent_request_lines = self.env['indent.request.line'].search([('id', 'in', selected_lines)])
        for request_line in indent_request_lines:
            if request_line.state == 'draft':
                raise UserError(_("Selected indent request line is in draft state."))
            
            if request_line.state == 'locked':
                raise UserError(_("Selected indent request line is in locked state"))

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Draft MO',
            'res_model': 'indent.request.line.make.manufacturing.order',
            'view_mode': 'form',
            'view_id': self.env.ref('harleys_customization.view_indent_request_line_make_manufacturing_order').id,
            'target': 'new',
            'context': {'active_ids': self.ids},
        }