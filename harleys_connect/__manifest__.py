{
    'name': "Harley's Connect",
    'summary': 'Synchronize Odoo Purchase Orders with Vendor Systems.',

    'description': """
Harley's Connect

Features
--------
* OTP Authentication
* Vendor Configuration
* Purchase Order Synchronization
* API Logging
* Webhook Integration
* Rista Reports (live fetch, no local storage yet)
* GRN Synchronization (Future)
""",

    'author': "Harley's",
    'category': 'Inventory/Purchase',
    'version': '19.0.1.0.0',

    'depends': [
        'base',
        'web',
        'product',
        'purchase',
        'stock',
        'contacts',
        'mail',
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/scheduled_jobs.xml',
        'views/menu.xml',
        'views/vendor_platform_views.xml',
        'views/vendor_account_views.xml',
        'views/vendor_outlet_views.xml',
        'views/vendor_api_log_views.xml',
        'views/vendor_webhook_log_views.xml',
        'views/purchase_order_views.xml',
        'views/product_supplierinfo_views.xml',
        'views/res_config_settings_views.xml',
        'views/rista_reports_actions.xml',
        'wizard/vendor_auth_wizard_views.xml',
        'wizard/vendor_order_confirm_wizard_views.xml',
        'reports/vendor_order_report.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'harleys_connect/static/src/rista_reports/**/*',
        ],
    },

    'images': [
        'static/description/banner.png',
    ],

    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
