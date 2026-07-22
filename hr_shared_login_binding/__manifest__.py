{
    'name': "HR Shared Login Employee Binding",

    'summary': "Attribute actions on shared/functional logins to the employee actually performing them",
    "version": "19.0.1.0.0",
    'description': """
        Some accounts (e.g. Purchase Manager, Accountant) are functional roles shared
        by more than one employee. This module adds an employee identity-verification
        step to the login flow for accounts flagged as shared: after the shared
        account's own credentials are accepted, the employee must additionally confirm
        their own personal login before the session is granted.

        The verification step reuses Odoo's native multi-factor-auth session mechanism
        (res.users._mfa_type/_mfa_url and the pre_uid/finalize session flow), the same
        one auth_totp uses, rather than adding a separate authentication layer.

    Once bound, the acting employee is logged alongside the functional account on
        every create/update of the business records this module is applied to,
        via chatter messages on the record: Purchase Orders, Indent Requests,
        Sales Orders, Invoices/Bills, Payments, Manufacturing Orders, Stock
        Transfers, Stock Scraps and Helpdesk Tickets.
    """,
    'category': 'Human Resources',
    'depends': [
        'base', 'web', 'hr', 'mail',
        'purchase', 'sale', 'account', 'stock', 'mrp', 'helpdesk',
        'harleys_customization',
    ],
    'data': [
        'views/res_users_views.xml',
        'views/employee_verify_templates.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
