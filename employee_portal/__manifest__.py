# -*- coding: utf-8 -*-
{
    'name': "Employee Portal",
    'version': '19.0.0.0.0',
    'summary': "Adding Hr Portal",
    'depends': [
        'base',
        'mrp',
        'portal',
        'hr_holidays',
        'hr',
        'hr_expense',
        'hr_payroll',
        'hr_attendance',
        'l10n_in_hr_payroll',
        'web'
    ],
    'category': 'Human Resources',
    'description': """Adding HR portal functionality to the employee""",
    'data': [
        'views/employee_attendance_portal_view.xml',
        'views/employee_allocation_portal_view.xml',
        'views/employee_timeoff_portal_view.xml',
        'views/employee_payslip_portal_view.xml',
        'views/res_users_view.xml',
        'security/payslip_portal_access.xml',
        'security/ir.model.access.csv',

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
