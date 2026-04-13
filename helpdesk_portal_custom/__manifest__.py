# -*- coding: utf-8 -*-
{
    'name': 'Helpdesk Portal Custom',
    'version': '19.0.1.0.0',
    'summary': 'More custom fields in helpdesk ticket portal form',
    'description': """
        Extends the helpdesk ticket portal form to include a custom
        fields.
    """,
    'category': 'Helpdesk',
    'author': 'Hari',
    'depends': [
        'helpdesk',
        'portal',
        'stock',
        'website',
    ],
    'data': [
        'views/helpdesk_portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'helpdesk_portal_custom/static/src/css/portal_form.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
