from odoo import models, fields, api, _
from odoo.exceptions import UserError

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    batch_size = fields.Float(related="product_id.batch_size", string="Batch Size")
    batch_qty = fields.Float()
    section = fields.Many2one(related="product_id.product_tmpl_id.section", string="Section", store=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('check_mo_bom_missing_from_indent'):
            self._check_products_have_bom(vals_list)
        return super().create(vals_list)

    def _check_products_have_bom(self, vals_list):
        products_by_company = {}
        for vals in vals_list:
            product_id = vals.get('product_id')
            if not product_id or vals.get('bom_id'):
                continue
            company_id = vals.get('company_id') or self.env.company.id
            products_by_company.setdefault(company_id, set()).add(product_id)

        for company_id, product_ids in products_by_company.items():
            company = self.env['res.company'].browse(company_id)
            products = self.env['product.product'].browse(product_ids).exists()
            for product in products:
                if not self._product_has_bom(product, company):
                    raise UserError(_(
                        "For the '%s' BOM missing contact your city head"
                    ) % product.display_name)

    def _product_has_bom(self, product, company=None):
        company = company or self.env.company
        return bool(self.env['mrp.bom'].search([
            '|',
            ('product_id', '=', product.id),
            '&',
            ('product_id', '=', False),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
            ('company_id', 'in', [company.id, False]),
        ], limit=1))

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
