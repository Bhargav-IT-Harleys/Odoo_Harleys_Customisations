{
    'name': "HR Shared Login Employee Binding",

    'summary': "Attribute actions on shared/functional logins to the employee actually performing them",
    "version": "19.0.1.0.0",
    'description': """
        Shared/functional accounts (e.g. Purchase Manager, Accountant) require an
        employee identity check at login before the session is granted, and every
        chatter message posted afterwards is tagged with that employee - see
        employee-attribution-current-state.md and docs/developer-guide.html for
        the full design. Settings > Harleys > Portal User Mapping provides an
        Excel/CSV upload for authorizing many employees against their
        functional accounts at once (requires openpyxl and xlsxwriter, both
        Python libraries rather than Odoo modules). stock.move.line also gets
        an Employee column next to core's own "Done By" on the History list
        (opened from Inventory Adjustments) - stock.quant itself has no
        reachable form/chatter to attribute to (list-only action), so this
        rides on the move line it produces instead.
    """,
    'category': 'Human Resources',
    'depends': ['base', 'web', 'hr', 'mail', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
        'views/employee_verify_templates.xml',
        'views/ir_model_views.xml',
        'views/attribution_log_views.xml',
        'views/stock_move_line_views.xml',
        'wizard/attribution_bulk_import_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
