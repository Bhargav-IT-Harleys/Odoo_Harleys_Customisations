from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    batch_size = fields.Float(related="product_id.batch_size", string="Batch Size")
    batch_qty = fields.Float()
    section = fields.Many2one(related="product_id.product_tmpl_id.section", string="Section", store=True)
    is_transfer_created = fields.Boolean(
        string="Transfer Created",
        default=False,
        readonly=True,
        copy=False,
        store=True,
        help="Indicates whether the transfer has been created."
        )
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type', copy=True, readonly=False,
        compute='_compute_custom_picking_type_id', store=True, precompute=True,
        domain="[('code', '=', 'mrp_operation')]",
        required=True, check_company=True, index=True)

    @api.depends('company_id', 'bom_id')
    def _compute_custom_picking_type_id(self):
        domain = [
            ('code', '=', 'mrp_operation'),
            ('warehouse_id.company_id', 'in', self.company_id.ids),
        ]
        if self.env.user.property_warehouse_id:
            domain += [('warehouse_id', 'in', self.env.user.property_warehouse_id.id)]
        picking_types = self.env['stock.picking.type'].search_read(domain, ['company_id'], load=False, limit=1)
        picking_type_by_company = {pt['company_id']: pt['id'] for pt in picking_types}
        default_picking_type_id = self.env.context.get('default_picking_type_id')
        default_picking_type = default_picking_type_id and self.env['stock.picking.type'].browse(default_picking_type_id)
        if not default_picking_type:
            default_warehouse_id = self.env.context.get('force_warehouse_id')
            default_picking_type = default_warehouse_id and self.env['stock.warehouse'].browse(default_warehouse_id).manu_type_id
        for mo in self:
            if default_picking_type and default_picking_type.company_id == mo.company_id:
                mo.picking_type_id = default_picking_type
                continue
            if mo.bom_id and mo.bom_id.picking_type_id:
                mo.picking_type_id = mo.bom_id.picking_type_id
                continue
            if mo.picking_type_id and mo.picking_type_id.company_id == mo.company_id:
                continue
            mo.picking_type_id = picking_type_by_company.get(mo.company_id.id, False)
            company_warehouse = self.env['stock.warehouse'].search([('company_id', '=', mo.company_id.id)], limit=1)
            if not company_warehouse:
                self.env['stock.warehouse']._warehouse_redirect_warning()
    
    def action_create_internal_transfer(self):
        selected_lines = self.browse(self.env.context.get('active_ids', []))


        if 'draft' in selected_lines.mapped('state') or 'confirmed' in selected_lines.mapped('state') or 'progress' in selected_lines.mapped('state') or 'to_close' in selected_lines.mapped('state') or 'cancel' in selected_lines.mapped('state'):
            raise UserError('Selected Manufacturing Orders is not in "Done" state')
            
        section_values = selected_lines.mapped('section')
        if len(section_values) > 1:
            raise UserError(_('Selected lines "section" is not same'))

        picking_type_values = selected_lines.mapped('picking_type_id')
        if len(picking_type_values) > 1:
            raise UserError(_('Selected lines "Operation Type" is not same'))

        mrp = self.env['mrp.production']
        mrp_records = mrp.search([('id', 'in', selected_lines)])
        for mrp_record in mrp_records:
            if mrp_record.is_transfer_created:
                raise UserError(f"Already Material Request created for this selected product - {mrp_record.product_id.display_name}")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Internal Transfer to store',
            'res_model': 'mo.internal.transfer.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('harleys_customization.view_mo_internal_transfer').id,
            'target': 'new',
            'context': {'active_ids': self.ids},
        }

class StockMove(models.Model):
    _inherit = "stock.move"

    mo_name = fields.Char(related='raw_material_production_id.name', string="MO Ref.")
    mo_product_qty = fields.Float(related="raw_material_production_id.product_qty", string="MO Qty")
    mo_date_start = fields.Datetime(related='raw_material_production_id.date_start', string="MO Schedule Date")
    mo_section = fields.Many2one('production.section', related='raw_material_production_id.section', string="Prod.Sect.")
    mo_product_uom_id = fields.Many2one('uom.uom', related='raw_material_production_id.product_uom_id', string="MO Prod.UOM")
    mo_product_id = fields.Many2one('product.product', string="MO Product", related='raw_material_production_id.product_id', store=True, readonly=True)
    categ_id = fields.Many2one('product.category', string="MO lines Prod.Catg.", related='product_id.categ_id', store=True, readonly=True)
    parent_categ_id = fields.Many2one('product.category', related='product_id.categ_id.parent_id', string="Parent Catg.", store=True)
    is_transfer_created = fields.Boolean(
        string="Transfer Created",
        default=False,
        readonly=True,
        copy=False,
        store=True,
        help="Indicates whether the transfer has been created."
        )

    def action_print_report(self):
        hy = self._get_grouped_data()
        return self.env.ref(
            'harleys_customization.action_report_mo_material_requirements'
        ).report_action(self)

    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.move'].browse(docids)
        company = self.env.company
        return {
            'doc_ids': docids,
            'doc_model': 'stock.move',
            'docs': docs,
            'company': company,
        }


    def _get_grouped_data(self):
        selected_lines = self.browse(self.env.context.get('active_ids', []))
        StockMove = self.env['stock.move']
        grouped_data = self.env['stock.move'].read_group(
            domain=[('raw_material_production_id','!=',False),
             ('raw_material_production_id.state','=','confirmed'),
             ('id', 'in',selected_lines)],
            fields=['mo_date_start', 'parent_categ_id', 'mo_section', 'product_id', 'product_uom_qty', 'packaging_uom_id'],  # only actual fields or aggregates
            groupby=['mo_date_start:day', 'parent_categ_id', 'mo_section', 'product_id'],
            lazy=False
        )
        return grouped_data

    def _get_grouped_4level(self):
        raw = self._get_grouped_data()
        import re
        from collections import OrderedDict

        tree = OrderedDict()

        for line in raw:
            date    = line.get('mo_date_start:day') or 'No Date'
            categ   = line['parent_categ_id']        # (id, name)
            section = line.get('mo_section')         # False or (id, name)
            prod    = line['product_id']             # (id, name)
            count   = line['__count']
            qty     = line['product_uom_qty'] or 0
            product_uom = self.env['product.product'].search([('id', '=', line['product_id'][0])], limit=1)
            uom     = product_uom.uom_id.name

            categ_key   = categ[0] if categ else 0
            categ_name  = categ[1] if categ else 'Uncategorized'
            section_key = section[0] if section else 0
            section_name= section[1] if section else 'No Section'
            uom_name    = uom if uom else ''
            product_qty = qty if qty else 0

            prod_full = prod[1]
            match = re.match(r'^\[(.+?)\]\s*(.*)', prod_full)
            prod_code = match.group(1) if match else ''
            prod_name = match.group(2) if match else prod_full

            if date not in tree:
                tree[date] = OrderedDict()

            if section_key not in tree[date]:
                tree[date][section_key] = {
                    'name': section_name,
                    'categories': OrderedDict(),
                    'total_count': 0,
                }

            if categ_key not in tree[date][section_key]['categories']:
                tree[date][section_key]['categories'][categ_key] = {
                    'name': categ_name,
                    'products': [],
                    'total_count': 0,
                }

            tree[date][section_key]['categories'][categ_key]['products'].append({
                'code': prod_code,
                'name': prod_name,
                'full_name': prod_full,
                'count': count,
                'uom': uom_name,
                'qty': product_qty,
            })

            tree[date][section_key]['categories'][categ_key]['total_count'] += count
            tree[date][section_key]['total_count'] += count

        result = []
        for date, sections in sorted(tree.items()):
            date_total = sum(s['total_count'] for s in sections.values())
            section_list = []
            for _, sec_data in sorted(sections.items(), key=lambda x: x[1]['name']):
                category_list = []
                for _, cat_data in sorted(sec_data['categories'].items(), key=lambda x: x[1]['name']):
                    cat_data['products'].sort(key=lambda p: p['code'])
                    category_list.append({
                        'name': cat_data['name'],
                        'products': cat_data['products'],
                        'total_count': cat_data['total_count'],
                    })
                section_list.append({
                    'name': sec_data['name'],
                    'categories': category_list,
                    'total_count': sec_data['total_count'],
                })
            result.append({
                'date': date,
                'sections': section_list,
                'total_count': date_total,
            })
        return result

    def action_create_internal_transfer(self):
        selected_lines = self.browse(self.env.context.get('active_ids', []))

        section_values = selected_lines.mapped('mo_section')
        if len(section_values) > 1:
            raise UserError(_('Selected lines "Production Section." is not same'))

        picking_type_values = selected_lines.mapped('picking_type_id')
        if len(picking_type_values) > 1:
            raise UserError(_('Selected lines "Operation Type" is not same'))

        stock_move = self.env['stock.move']
        stock_move_lines = stock_move.search([('id', 'in', selected_lines)])
        for stock_move_line in stock_move_lines:
            if stock_move_line.is_transfer_created:
                raise UserError(f"Already Material Request created for this selected product - {stock_move_line.product_id.display_name}")

        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Material Request',
            'res_model': 'mol.internal.transfer.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('harleys_customization.view_mol_internal_transfer').id,
            'target': 'new',
            'context': {'active_ids': self.ids},
        }