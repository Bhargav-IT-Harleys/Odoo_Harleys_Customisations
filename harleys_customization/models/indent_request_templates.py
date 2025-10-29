from odoo import models, fields, api, _
from datetime import date


class IndentRequestTemplates(models.Model):
    _name = 'indent.request.templates'
    _description = 'Indent Request Templates'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    name = fields.Char(
        string="Template Name",
        required=True,
        tracking=True,
    )

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

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=_company_get,
        tracking=True,
    )
    

    line_ids = fields.One2many(
        comodel_name="indent.request.line.templates",
        inverse_name="request_id",
        string="Products to Manufacturing",
        readonly=False,
        copy=True,
        tracking=True,
    )

    def copy(self, default=None):
        default = dict(default or {})
        self.ensure_one()
        return super().copy(default)


class IndentRequestLineTemplates(models.Model):
    _name = 'indent.request.line.templates'
    _description = 'Indent Request Line Templates'


    request_id = fields.Many2one(
        comodel_name="indent.request.templates",
        string="Indent Request Templates",
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