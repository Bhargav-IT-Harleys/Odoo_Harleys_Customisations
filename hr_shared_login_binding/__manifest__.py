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

Once bound, the acting employee is attached to chatter messages via two
        layers on mail.thread (models/message_attribution.py), both applying
        automatically to every chatter-enabled model - present and future -
        with no per-model wiring:

        1. Always on: mail.thread's low-level _message_create() is enriched
           with an employee_id and a short "Logged by <employee>" note,
           wherever a message was already going to be posted (manual notes,
           Discuss, field-tracking messages).
        2. Opt-in per model: an explicit "Created/Updated/Deleted" note for
           models/fields the above can't reach (untracked fields, line items
           with no chatter panel of their own). Toggled per model from
           Settings > Technical > Models (see models/attribution_config.py) -
           off by default, so installing a new module never enables this on
           its own; an admin deliberately turns it on per model, no code
           change required.

        An earlier, static per-model create/write implementation (models/
        attribution_targets.py) is kept in the codebase but disabled, as a
        fallback/reference only. point_of_sale is intentionally left
        untouched by either mechanism, since pos_hr already attributes orders
        to the badged-in cashier natively.
    """,
    'category': 'Human Resources',
    'depends': [
        'base', 'web', 'hr', 'mail',
        'purchase', 'purchase_requisition',
        'sale', 'sales_team',
        'account', 'account_asset', 'account_batch_payment', 'account_loans',
        'account_reports', 'account_accountant', 'analytic',
        'stock', 'stock_landed_costs', 'stock_picking_batch',
        'mrp', 'quality',
        'hr_expense', 'hr_holidays', 'hr_payroll', 'hr_attendance',
        'helpdesk', 'project', 'product', 'fleet', 'calendar',
        'l10n_in', 'l10n_in_ewaybill',
        'harleys_customization',
    ],
    'data': [
        'views/res_users_views.xml',
        'views/employee_verify_templates.xml',
        'views/ir_model_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
