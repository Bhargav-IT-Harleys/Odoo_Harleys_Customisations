from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import UserError


class IndentRequestTemplates(models.Model):
    _name = 'indent.request.templates'
    _description = 'Indent Request Templates'
    _company_id_field = 'company_id'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]

    @api.model
    def _company_get(self):
        return self.env["res.company"].browse(self.env.company.id)

    name = fields.Char(
        string="Template Name",
        tracking=True,
        store=True
    )

    current_date = fields.Date(
        string='Date',
        default=lambda self: date.today()
    )

    delivery_from = fields.Many2one(
        'stock.warehouse',
        string='Delivery From',
        related='picking_type_id.warehouse_id',
        store=True
    )


    via_location_id = fields.Many2one('stock.location', string="Delivery Via", required=True, default=lambda self: self.env['stock.location'].search(
        [('usage', '=', 'transit')], limit=1).id)

    delivery_to = fields.Many2one(
        'stock.warehouse',
        string='Delivery To',
        related='via_picking_type_id.warehouse_id',
        required=True
    )
    picking_type_id = fields.Many2one('stock.picking.type', string="Operation From", help="This defines the first stock movement from the Central Store to the Transit location. When the indent is confirmed, the products will first move out from the Central Store and reach the Transit location. Example: TGCS/Stock → Transit")
    via_picking_type_id = fields.Many2one('stock.picking.type', string="Operation To", help="This defines the second stock movement from the Transit location to the Outlet location. When the indent is confirmed, and first move is completed the products will move out from Transit location to Outlet location. Example: Transit → TG-Ivory Lounge Nanakramguda")

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=False,
        default=_company_get,
        tracking=True,
    )
    
    employee_ids = fields.Many2many('hr.employee', string="Employee")
    password = fields.Char(string="Password", copy=False)
    retype_password = fields.Char(string="Re-Enter Password", copy=False)

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
        base_name = f"{self.delivery_to.name} Indent Template" if self.delivery_to else "Indent Template"

        existing_templates = self.env['indent.request.templates'].search([
            ('name', 'ilike', base_name)
        ])

        if not existing_templates:
            new_name = f"{base_name} - 1"
        else:
            count = len(existing_templates)
            new_name = f"{base_name} - {count+1}"

        default['name'] = new_name
        return super(IndentRequestTemplates, self).copy(default)

    @api.constrains('password', 'retype_password')
    def _check_password_match(self):
        for rec in self:
            if rec.password and rec.retype_password:
                if rec.password != rec.retype_password:
                    raise UserError("Password and Re-Enter Password do not match.")

    @api.onchange("delivery_to")
    def _onchange_delivery_to(self):
        if self.delivery_to:
            base_name = f"{self.delivery_to.name} Indent Template"

            existing_templates = self.env['indent.request.templates'].search([
                ('name', 'ilike', base_name)
            ])

            if not existing_templates:
                self.name = f"{base_name} - 1"
            else:
                count = len(existing_templates)
                self.name = f"{base_name} - {count+1}"

class IndentRequestLineTemplates(models.Model):
    _name = 'indent.request.line.templates'
    _description = 'Indent Request Line Templates'
    _company_id_field = 'company_id'


    request_id = fields.Many2one(
        comodel_name="indent.request.templates",
        string="Indent Request Templates",
        ondelete="cascade",
        readonly=True,
        index=True,
    )

    name = fields.Char(string="Description")
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        required=True,
    )
    categ_id = fields.Many2one(string="Product Category", related='product_id.categ_id', readonly=True)
    default_code = fields.Char(string="Internal Reference", related="product_id.default_code")
    hsn_code = fields.Char(string="HSN/SAC Code")
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM"
    )
    product_qty = fields.Float(
        string="Qty", digits="Product Unit of Measure"
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
