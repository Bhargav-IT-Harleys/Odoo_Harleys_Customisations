from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import get_lang

class IndentRequestLineMakeManufacturingOrder(models.TransientModel):
    _name = "indent.request.line.make.manufacturing.order"
    _description = "Indent Request Line Make Manufacturing Order"

    @api.model
    def default_get(self, fields_list):
        res = super(IndentRequestLineMakeManufacturingOrder, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            records = self.env['indent.request.line'].browse(active_ids)
            res.update({"indent_request_line_ids" : [(0, 0, {"name": record.name, 
                                                                "source_line_id": record.id,
                                                                "product_id": record.product_id, 
                                                                "default_code": record.default_code, 
                                                                "hsn_code": record.hsn_code,
                                                                "product_uom_id": record.product_uom_id, 
                                                                "product_qty": record.product_qty, 
                                                                "comments": record.comments, 
                                                                "indent_number": record.indent_number,}) for record in records]
                })
        return res
    
    indent_request_line_ids = fields.One2many(
        comodel_name="indent.request.line.wizard",
        inverse_name="request_id",
        string="Indent Request to Manufacturing",
        readonly=False,
        store=True
    )
    
    def make_manufacturing_order(self):
        if self.indent_request_line_ids:
            merged = {}
            for line in self.indent_request_line_ids:
                line.source_line_id.state = 'locked'
                pid = line.product_id.id
                qty = line.product_qty
                origin = line.indent_number

                if pid in merged:
                    merged[pid]['product_qty'] += qty
                    if origin:
                        merged[pid]['origin'] += f",{origin}"
                else:
                    merged[pid] = {
                        'product_id': pid,
                        'product_qty': qty,
                        'origin': origin,
                    }
                indent_source = self.env['indent.request'].search([('id', '=', line.source_line_id.request_id.id)], limit=1)
                indent_source.state_checker()
            data_dict = list(merged.values())
            return self.env['mrp.production'].create(data_dict)

class IndentRequestLineWizard(models.TransientModel):
    _name = 'indent.request.line.wizard'
    _description = 'Indent Request Line Wizard'


    request_id = fields.Many2one(
        comodel_name="indent.request.line.make.manufacturing.order",
        string="Indent Request Wizard",
        ondelete="cascade",
        store=True
    )

    name = fields.Char(string="Description", tracking=True, store=True)
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        domain=[("purchase_ok", "=", True)],
        tracking=True,
        store=True
    )
    default_code = fields.Char(string="Internal Reference", related="product_id.default_code", store=True)
    hsn_code = fields.Char(string="HSN/SAC Code", store=True)
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        related="product_id.uom_id",
        domain="[('category_id', '=', product_uom_category_id)]",
        store=True
    )
    product_qty = fields.Float(
        string="Qty", tracking=True, digits="Product Unit of Measure",
        store=True
    )
    comments = fields.Char(string="Comments", store=True)


    indent_number = fields.Char(
        string="Indent Number",
        store=True
    )

    source_line_id = fields.Many2one(
        comodel_name="indent.request.line",
        string="Indent Request",
        readonly=True,
        store=True
    )

