from datetime import datetime, time, timedelta

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MergeMrpProductionWizard(models.TransientModel):
    _name = "merge.mrp.production.wizard"
    _description = "Merge Manufacturing Order Wizard"

    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        readonly=True,
    )
    schedule_date = fields.Date(string="Schedule Date", required=True)
    finished_goods_location_id = fields.Many2one(
        "stock.location",
        string="Finished Goods Location",
        domain="[('usage', '=', 'internal')]",
        required=True,
        check_company=True,
    )
    select_all_sections = fields.Boolean(string="Select All Sections")
    section_ids = fields.Many2many(
        "production.section",
        string="Section",
        required=True,
    )

    def _get_all_sections(self):
        return self.env["production.section"].search([])

    @api.onchange("select_all_sections")
    def _onchange_select_all_sections(self):
        for wizard in self:
            wizard.section_ids = (
                wizard._get_all_sections()
                if wizard.select_all_sections
                else False
            )

    def _get_mo_domain(self):
        self.ensure_one()
        if not self.section_ids:
            raise UserError(_("Please select at least one section."))

        return (
            self._get_date_domain()
            + [
                ("location_dest_id", "=", self.finished_goods_location_id.id),
                ("section", "in", self.section_ids.ids),
                ("is_merged", "=", False),
            ]
        )

    def _get_date_domain(self):
        self.ensure_one()
        user_tz = pytz.timezone(self.env.user.tz or "UTC")
        local_start = user_tz.localize(datetime.combine(self.schedule_date, time.min))
        local_end = local_start + timedelta(days=1)
        utc_start = local_start.astimezone(pytz.UTC).replace(tzinfo=None)
        utc_end = local_end.astimezone(pytz.UTC).replace(tzinfo=None)

        return [
            ("date_start", ">=", fields.Datetime.to_string(utc_start)),
            ("date_start", "<", fields.Datetime.to_string(utc_end)),
            ("state", "in", ['draft', 'confirmed']),
            ("is_merged", "=", False)
        ]

    def action_merge_manufacturing_orders(self):
        self.ensure_one()
        productions = self.env["mrp.production"].search(self._get_mo_domain())

        if not productions:
            raise UserError(_("No Manufacturing Orders found for the selected filters."))
        products_group = productions.grouped('product_id')
        for product, production in products_group.items():
            if len(production) > 1:
                production.action_merge()
        return True
