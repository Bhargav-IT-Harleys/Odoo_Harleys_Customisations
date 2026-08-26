{
    'name': "Harley's Shared Login & Audit Trail",

    'summary': "Attribute actions on shared/functional logins to the employee actually performing them",
    "version": "19.0.1.0.0",
    'author': "Harley's",
    'description': """
        Shared/functional accounts (e.g. Purchase Manager, Accountant) require an
        employee identity check at login before the session is granted, and every
        chatter message posted afterwards is tagged with that employee - see
        employee-attribution-current-state.md and docs/developer-guide.html for
        the full design. Settings > Harley's > Portal User Mapping provides an
        Excel/CSV upload for authorizing many employees against their
        functional accounts at once (requires openpyxl and xlsxwriter, both
        Python libraries rather than Odoo modules). stock.move.line also gets
        an Employee column next to core's own "Done By" on the History list
        (opened from Inventory Adjustments) - stock.quant itself has no
        reachable form/chatter to attribute to (list-only action), so this
        rides on the move line it produces instead. The systray also shows
        who's acting on the session (account name, plus the verified
        employee for shared logins), and on every login blacks out the
        screen and auto-opens the company switcher so users must explicitly
        pick their active companies before continuing - dismissed only by
        actually confirming a selection there.
    """,
    'category': 'Human Resources',
    'depends': ['base', 'web', 'hr', 'mail', 'stock', 'auth_timeout'],
    'data': [
        'security/ir.model.access.csv',
        'data/attribution_config_data.xml',
        'views/res_users_views.xml',
        'views/chatter_views.xml',
        'views/employee_verify_templates.xml',
        'views/ir_model_views.xml',
        'views/attribution_log_views.xml',
        'views/stock_move_line_views.xml',
        'wizard/attribution_bulk_import_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_shared_login_binding/static/src/systray/employee_name_systray.js',
            'hr_shared_login_binding/static/src/systray/employee_name_systray.xml',
            'hr_shared_login_binding/static/src/systray/employee_name_systray.scss',
            'hr_shared_login_binding/static/src/company_selection/company_selection.js',
            'hr_shared_login_binding/static/src/company_selection/company_selection.xml',
            'hr_shared_login_binding/static/src/company_selection/company_selection.scss',
            'hr_shared_login_binding/static/src/auth_timeout/inactivity_logout.js',
        ],
        'web.assets_frontend': [
            'hr_shared_login_binding/static/src/auth_timeout/inactivity_logout.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
