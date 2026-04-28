{
    'name': "Harleys Customization",

    'summary': "Harleys Customization",
    "version": "19.0.0.0.0",
    'description': """
           Harleys Customization
    """,
    'category': 'Customizations',
    'depends': ['base','web', 'stock','mrp', 'helpdesk'],
    'data': [
        'security/security_group.xml',
        'security/ir.model.access.csv',
        'security/helpdesk_tag_portal_access.xml',
        'views/indent_request_views.xml',
        'views/indent_request_template_views.xml',
        'data/indent_request_sequence.xml',
        'wizard/indent_request_line_make_manufacturing_orders_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/contact_views.xml',
        'views/mrp_production_views.xml',
        'views/service_type_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/helpdesk_portal_template.xml',
        'reports/manufacturing_order_lines_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

