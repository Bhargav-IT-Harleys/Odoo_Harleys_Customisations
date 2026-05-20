from datetime import datetime, timedelta
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import get_lang


class MolInternalTransferWizard(models.TransientModel):
    _name = "mol.internal.transfer.wizard"
    _description = "Mol to Internal Transfer Wizard"

    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        required=True, index=True,
        tracking=True)
    location_id = fields.Many2one(
        'stock.location', "Source Location",
        store=True, precompute=True, readonly=False,
        check_company=True, required=True)
    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        store=True, precompute=True, readonly=False,
        check_company=True, required=True)

    button_visible = fields.Boolean(default=False)

    @api.onchange("picking_type_id")
    def _onchange_picking_type(self):
        if self.picking_type_id:
            self.location_id = self.picking_type_id.default_location_src_id.id
            self.location_dest_id = self.picking_type_id.default_location_dest_id.id


    @api.model
    def default_get(self, fields_list):
        res = super(MolInternalTransferWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        merged = {}
        if active_ids:
            records = self.env['stock.move'].browse(active_ids)
            for record in records:
                pid = record.product_id.id

                if pid in merged:
                    merged[pid]['demanded_qty'] += record.product_qty
                    merged[pid]['mo_number'] += f", ({record.mo_name}, {record.mo_section.name})"
                else:
                    merged[pid] = {"product_id": record.product_id,
                                "product_uom_id": record.product_uom,
                                "demanded_qty": record.product_uom_qty,
                                "mo_number": f"({record.mo_name}, {record.mo_section.name})"}
            res["internal_transfer_line_wizard_ids"] = [
            (0, 0, vals) for vals in merged.values()
        ]
        return res
    
    internal_transfer_line_wizard_ids = fields.One2many(
        comodel_name="mol.internal.transfer.line.wizard",
        inverse_name="internal_transfer_wizard_id",
        string="Mol Internal Transfer Line Wizard",
        readonly=False,
        store=True
    )
            
    def make_internal_transfer_draft(self):
        """Create internal transfers in draft state strictly within the current active company."""
        self.ensure_one()
        active_ids = self.env.context.get('active_ids', [])
        current_company = self.env.company

        source_location = self.location_id
        dest_location = self.location_dest_id
        picking_type = self.picking_type_id

        if source_location.id == dest_location.id:
            raise UserError("Source Location and the Destination Location should not be same.")

        for loc in [source_location, dest_location]:
            if loc.company_id and loc.company_id.id != current_company.id:
                raise UserError("Location '%s' does not belong to your current company: %s" % (
                    loc.display_name, current_company.name))

        origin_list = [origin_line.mo_number for origin_line in self.internal_transfer_line_wizard_ids]
        origin = ", ".join(set(origin_list))
                    
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            # 'scheduled_date': ,
            'origin': origin,
            'company_id': current_company.id,
        })

        for line_data in self.internal_transfer_line_wizard_ids:
            move1 = self.env['stock.move'].create({
                'product_id': line_data.product_id.id,
                'product_uom_qty': line_data.demanded_qty,
                'product_uom': line_data.product_uom_id.id,
                'picking_id': picking.id,
                'company_id': current_company.id,
            })

        picking.action_confirm()
        active_records = self.env['stock.move'].browse(active_ids)
        for active_record in active_records:
            active_record.is_transfer_created = True
        self.button_visible = True
        return self.env.ref('stock.action_report_picking').report_action(picking)

class MolInternalTransferLineWizard(models.TransientModel):
    _name = 'mol.internal.transfer.line.wizard'
    _description = 'Mol Internal Transfer Line Wizard'


    internal_transfer_wizard_id = fields.Many2one(
        comodel_name="mol.internal.transfer.wizard",
        string="Mol Internal Transfer Wizard",
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
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="UoM",
        related="product_id.uom_id",
        domain="[('category_id', '=', product_uom_category_id)]",
        store=True
    )
    demanded_qty = fields.Float(
        string="Demanded Qty", tracking=True, digits="Product Unit", store=True)

    mo_number = fields.Char(
        string="MO Number",
        store=True
    )
