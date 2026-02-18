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
import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    """Add new fields to configuration settings to Restrict stock warehouse
    for users."""
    _inherit = 'res.config.settings'

    group_user_warehouse_restriction = fields.Boolean(
        string="Restrict Stock Warehouse",
        implied_group='user_warehouse_restriction.'
                      'user_warehouse_restriction_group_user',
        help="Check if you want to restrict warehouse for users.")

    @api.onchange('group_user_warehouse_restriction')
    def _onchange_group_user_warehouse_restriction(self):
        """This method is triggered when the 'group_user_warehouse_restriction'
        field is changed. if it's true, assigns the current user as the
        allowed user of all existing warehouses."""
        
        # Get all record rules that might interfere
        all_rules = self.env['ir.rule'].sudo().search([
            ('model_id.model', 'in', ['res.users', 'stock.warehouse', 'stock.picking.type'])
        ])
        
        # Store original active states
        original_states = {rule.id: rule.active for rule in all_rules}
        
        try:
            # Temporarily deactivate all related rules
            all_rules.write({'active': False})
            
            # Use sudo to bypass all access restrictions
            warehouses = self.env['stock.warehouse'].sudo().search([])
            
            for warehouse in warehouses:
                if self.group_user_warehouse_restriction:
                    # Assign the current user to each warehouse
                    if not warehouse.user_ids:
                        warehouse.write({'user_ids': [(6, 0, [self.env.user.id])]})
                else:
                    # Clear the allowed users for each warehouse
                    warehouse.write({'user_ids': [(5, 0, 0)]})
                    
        except Exception as e:
            _logger.error(f"Error updating warehouse users: {e}")
            raise
        finally:
            # Restore original active states
            for rule in all_rules:
                rule.write({'active': original_states[rule.id]})