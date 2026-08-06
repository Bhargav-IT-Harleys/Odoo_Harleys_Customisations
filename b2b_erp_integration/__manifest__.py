{
    'name': 'B2B ERP Integration',
    'summary': 'Synchronize Odoo Purchase Orders with Vendor Systems.',

    'description': """
        B2B ERP Integration

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
        'data/scheduled_jobs.xml',
        'data/mail_templates.xml',
        'views/menu.xml',
        'views/vendor_platform_views.xml',
        'views/vendor_account_views.xml',
        'views/vendor_outlet_views.xml',
        'views/vendor_api_log_views.xml',
        'views/vendor_webhook_log_views.xml',
        'views/purchase_order_views.xml',
        'wizard/vendor_auth_wizard_views.xml',
        'wizard/sync_products_wizard_views.xml',
        'reports/vendor_order_report.xml',
    ],

    'images': [
        'static/description/banner.png',
    ],

    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
