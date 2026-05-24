# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Unnimaya CO (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import models


class StockQuant(models.Model):
    """Restrict physical inventory quants by the user's allowed warehouses."""
    _inherit = 'stock.quant'

    def _apply_user_warehouse_restriction(self):
        """Return whether the current user should be limited by warehouse."""
        return self.env.user.has_group(
            'user_warehouse_restriction.user_warehouse_restriction_group_user')

    def _get_user_allowed_warehouse_ids(self):
        """Return warehouse ids allowed for the current inventory user."""
        return self.env.user.allowed_warehouse_ids.ids

    def _domain_location_id(self):
        """Limit selectable inventory count locations to allowed warehouses."""
        if not self._apply_user_warehouse_restriction():
            return super()._domain_location_id()

        allowed_warehouse_ids = self._get_user_allowed_warehouse_ids()
        if self.env.user.has_group('stock.group_stock_user'):
            return (
                "[('usage', 'in', ['internal', 'transit']), "
                "('warehouse_id', 'in', %s)] if context.get('inventory_mode') "
                "else []"
            ) % allowed_warehouse_ids
        return "[]"

    def action_view_inventory(self):
        """Show only allowed warehouse quants in Physical Inventory."""
        action = super().action_view_inventory()
        if self._apply_user_warehouse_restriction():
            allowed_warehouse_ids = self._get_user_allowed_warehouse_ids()
            action['context'] = dict(action.get('context') or {})
            action['context'].update({
                'restrict_inventory_locations': True,
                'user_allowed_warehouse_ids': allowed_warehouse_ids,
            })
            action['domain'] = action.get('domain', []) + [
                ('location_id.warehouse_id', 'in', allowed_warehouse_ids)
            ]
        return action
