from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import get_lang


class IndentRequestLineMakeManufacturingOrder(models.TransientModel):
    _name = "indent.request.line.make.manufacturing.order"
    _description = "Indent Request Line Make Manufacturing Order"

    @api.model
    def default_get(self, fields_list):
        res = super(IndentRequestLineMakeManufacturingOrder, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        route_id = self.env['stock.route'].search([("name", "=", "Manufacture")], limit=1)
        merged = {}
        if active_ids:
            records = self.env['indent.request.line'].browse(active_ids)
            for record in records:
                if route_id not in record.product_id.route_ids:
                    continue

                pid = record.product_id.id

                if pid in merged:
                    # merged[pid]['product_qty'] += record.product_qty
                    merged[pid]['demanded_qty'] += record.product_qty
                    merged[pid]['indent_number'] += f", {record.indent_number}"
                else:
                    merged[pid] = {"name": record.name, 
                                "source_line_id": record.id,
                                "product_id": record.product_id, 
                                "default_code": record.default_code, 
                                "hsn_code": record.hsn_code,
                                "product_uom_id": record.product_uom_id, 
                                # "product_qty": record.product_qty, 
                                "demanded_qty": record.product_qty, 
                                "comments": record.comments, 
                                "indent_number": record.indent_number,}
            res["indent_request_line_ids"] = [
            (0, 0, vals) for vals in merged.values()
        ]
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
            origin_merged = {}
            internal_transfer_merged = {}
            for line in self.indent_request_line_ids:
                line.source_line_id.state = 'locked'
                pid = line.product_id.id
                qty = line.product_qty
                product_uom = line.product_uom_id.id
                origin = line.indent_number
                self.check_product_has_bom(pid)

                if pid in merged:
                    merged[pid]['product_qty'] += qty
                    if origin:
                        merged[pid]['origin'] += f",{origin}"
                else:
                    merged[pid] = {
                        'product_id': pid,
                        'product_qty': qty,
                        'origin': origin,
                        'product_uom_id': product_uom,
                        'batch_qty': line.batch_qty,
                    }

            active_ids = self.env.context.get('active_ids', [])
            origin_indent_request_line = self.env['indent.request.line'].search([('id', 'in', active_ids)])
            for origin_line in origin_indent_request_line:
                origin_line.state = 'locked'
                pid = origin_line.product_id.id
                qty = origin_line.product_qty
                product_uom = origin_line.product_uom_id.id
                origin = origin_line.indent_number

                if pid in origin_merged:
                    origin_merged[pid]['product_qty'] += qty
                    if origin:
                        origin_merged[pid]['origin'] += f",{origin}"
                else:
                    origin_merged[pid] = {
                        'product_id': pid,
                        'product_qty': qty,
                        'origin': origin,
                        'product_uom_id': product_uom,
                    }
                indent_source = self.env['indent.request'].search([('id', '=', origin_line.request_id.id)], limit=1)
                if indent_source:
                    if origin in internal_transfer_merged:
                        internal_transfer_merged[origin]['lines'] += [{'product_id': pid,
                                                                        'product_qty': qty,
                                                                        'origin': origin,
                                                                        'product_uom_id': product_uom,
                                                                    }]
                    else:
                        internal_transfer_merged[origin] = {'delivery_from': indent_source.delivery_from.lot_stock_id.id,

                                                            'delivery_via' : indent_source.via_location_id.id,
                                                            'delivery_to' : indent_source.delivery_to.lot_stock_id.id,

                                                            # 'delivery_to' : indent_source.delivery_to.lot_stock_id.id,
                                                            'picking_type_id' : indent_source.picking_type_id.id,
                                                            'via_picking_type_id' : indent_source.via_picking_type_id.id,

                                                            'scheduled_date': indent_source.received_date,
                                                            'lines': [{'product_id': pid,
                                                                        'product_qty': qty,
                                                                        'origin': origin,
                                                                        'product_uom_id': product_uom,
                                                                    }]}
                indent_source.state_checker()

            data_dict = list(merged.values())
            self.make_internal_transfer_draft(internal_transfer_merged)
            return self.env['mrp.production'].create(data_dict)
        

    def make_internal_transfer_draft(self, internal_transfer_data):
        """Create internal transfers in draft state strictly within the current active company."""
        self.ensure_one()

        current_company = self.env.company

        for data in internal_transfer_data:
            source_location = self.env['stock.location'].sudo().browse(internal_transfer_data[data]['delivery_from'])
            dest_location = self.env['stock.location'].sudo().browse(internal_transfer_data[data]['delivery_to'])
            via_location = self.env['stock.location'].sudo().browse(internal_transfer_data[data]['delivery_via'])
            picking_type = self.env['stock.picking.type'].sudo().browse(internal_transfer_data[data]['picking_type_id'])
            via_picking_type = self.env['stock.picking.type'].sudo().browse(internal_transfer_data[data]['via_picking_type_id'])

            for loc in [source_location, dest_location]:
                if loc.company_id and loc.company_id.id != current_company.id:
                    raise UserError("Location '%s' does not belong to your current company: %s" % (
                        loc.display_name, current_company.name))

            # picking_type = self.env['stock.picking.type'].search([
            #     ('code', '=', 'internal'),
            #     ('company_id', '=', current_company.id)
            # ], limit=1)

            # if not picking_type:
            #     raise UserError("No internal picking type found for your current company: %s" % current_company.name)

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': source_location.id,
                'location_dest_id': via_location.id,
                'scheduled_date': internal_transfer_data[data]['scheduled_date'],
                'origin': data,
                'company_id': current_company.id,
            })
            picking_next_transfer = self.env['stock.picking'].create({
                'picking_type_id': via_picking_type.id,
                'location_id': via_location.id,
                'location_dest_id': dest_location.id,
                'scheduled_date': internal_transfer_data[data]['scheduled_date'],
                'origin': data,
                'company_id': current_company.id,
            })

            for line_data in internal_transfer_data[data]['lines']:
                move1 = self.env['stock.move'].create({
                    'product_id': line_data['product_id'],
                    'product_uom_qty': line_data['product_qty'],
                    'product_uom': line_data['product_uom_id'],
                    'picking_id': picking.id,
                    'location_id': source_location.id,
                    'location_dest_id': via_location.id,
                    'company_id': current_company.id,
                })
                move2 = self.env['stock.move'].create({
                    'product_id': line_data['product_id'],
                    'product_uom_qty': line_data['product_qty'],
                    'product_uom': line_data['product_uom_id'],
                    'picking_id': picking_next_transfer.id,
                    'location_id': via_location.id,
                    'location_dest_id': dest_location.id,
                    'company_id': current_company.id,
                })
                move1.move_dest_ids = [(4, move2.id)]
                move2.move_orig_ids = [(4, move1.id)]

            picking.action_confirm()
            picking_next_transfer.action_confirm()

        return True


    def check_product_has_bom(self, product_id):
        """Raise ValidationError if the product has no BoM in current company or globally shared."""
        product = self.env['product.product'].browse(product_id)
        company = self.env.company

        has_bom = self.env['mrp.bom'].search([
            '|',
            ('product_id', '=', product.id),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('company_id', 'in', [company.id, False])
        ], limit=1)

        if not has_bom:
            raise ValidationError(
                "Product '%s' does not have a Bill of Materials defined for company '%s' or globally." %
                (product.display_name, company.name)
            )








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
        string="Production Qty", tracking=True, digits="Product Unit of Measure", store=True, compute="_compute_product_qty")
    demanded_qty = fields.Float(string="Demanded Qty", readonly=True, store=True)
    comments = fields.Char(string="Comments", store=True)
    batch_size = fields.Float(string="Batch Size", related="product_id.batch_size")
    batch_qty = fields.Float(string="No. of Batch's", compute="_compute_no_of_batches", store=True)

    @api.depends('batch_qty', 'batch_size')
    def _compute_product_qty(self):
        for line in self:
            if line.batch_qty > 0 and line.batch_size > 0:
                line.product_qty = line.batch_qty * line.batch_size
            else:
                line.product_qty = 0.0

    @api.depends('demanded_qty','batch_size')
    def _compute_no_of_batches(self):
        for record in self:
            if record.demanded_qty <= record.batch_size:
                record.batch_qty = 1
            else:
                record.batch_qty=(record.demanded_qty - 1) // record.batch_size + 1


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

