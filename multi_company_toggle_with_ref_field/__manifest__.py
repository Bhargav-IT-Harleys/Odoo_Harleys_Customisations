# -*- coding: utf-8 -*-
{
    'name': "Multicompany toggle with ref field",

    'description': """
       Multicompany toggle with ref field
    """,
    'author': "Hari",
    'website': "https://aspireal.com/",
    'category': 'Customizations',
    'version': '0.1',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'multi_company_toggle_with_ref_field/static/src/multi_company_reference/multi_company_reference.js',
            'multi_company_toggle_with_ref_field/static/src/multi_company_reference/multi_company_reference.xml',
        ],
    },
    'license': 'LGPL-3',
    'application': False,
}

