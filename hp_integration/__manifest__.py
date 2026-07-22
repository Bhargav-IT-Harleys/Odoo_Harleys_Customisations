{
    'name': 'Hyperpure B2B ERP Integration',
    'summary': 'Synchronize Odoo Purchase Orders with Hyperpure.',

    'description': """
        Hyperpure B2B ERP Integration

        Features
        --------
        * OTP Authentication
        * Vendor Configuration
        * Product Mapping
        * Purchase Order Synchronization
        * API Logging
        * Webhook Integration
        * GRN Synchronization (Future)
        """,

    'author': 'Bhargav',
    'category': 'Inventory/Purchase',
    'version': '19.0.1.0.0',

    'depends': [
        'base',
        'purchase',
        'stock',
        'contacts',
        'mail',
    ],

    'data': [
        'security/ir.model.access.csv',

        'data/ir_config_parameter.xml',
        'data/cron.xml',

        'views/hp_config_views.xml',
        'views/purchase_order_views.xml',
        'views/hp_order_log_views.xml',

        'wizard/hp_otp_wizard_views.xml',
    ],

    'images': [
        'static/description/banner.png',
    ],

    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}