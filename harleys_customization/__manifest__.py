{
    'name': "Harleys Customization",

    'summary': "Harleys Customization",
    "version": "19.0.0.0.0",
    'description': """
           Harleys Customization
    """,
    'category': 'Customizations',
    'depends': ['base','web', 'stock'],
    'data': [
        'security/security_group.xml',
        'security/ir.model.access.csv',
        'views/indent_request_views.xml',
        'views/indent_request_template_views.xml',
        'data/indent_request_sequence.xml',
        'wizard/indent_request_line_make_manufacturing_orders_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/contact_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

