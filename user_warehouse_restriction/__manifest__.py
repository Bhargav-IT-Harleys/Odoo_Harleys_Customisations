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
{
    'name': "User Warehouse Restriction",
    'version': '19.0.1.0.0',
    'author': 'Cybrosys Technologies',
    'license': 'AGPL-3',
    'category': 'Warehouse',
    'summary': """Restrict Warehouses and location for users.""",
    'description': """This module helps you to restrict warehouse and stock 
     location for the specific users. So that users can only access the allowed
     warehouse and locations.""",
    'depends': ['stock_sms', 'harleys_customization'],
    'data': [
        'security/user_warehouse_restriction_groups.xml',
        'security/user_warehouse_restriction_security.xml',
        'views/res_config_settings_views.xml',
        'views/stock_warehouse_views.xml',
        'views/res_users_views.xml',
        'views/stock_quant_views.xml',
        # 'views/mrp_production_views.xml', #MO line visible based on the user selected warehouse.
    ],
    'images': ['static/description/banner.jpg'],
    'application': False,
}
