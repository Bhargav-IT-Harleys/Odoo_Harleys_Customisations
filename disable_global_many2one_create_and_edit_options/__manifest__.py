{
    'name': "Disable Many2One Create/Edit Options",

    'summary': 'Globally disables "Create" and "Create and Edit" options in many2one fields across all modules.',

    'description': """
                    This module applies a global override to remove the "Create" and "Create and Edit" options from all many2one fields in Odoo 19 Enterprise.
                    Features:
                    - OWL registry patch for consistent UI behavior
                    - No need to modify individual views
                    - Compatible with all Enterprise modules
                    - Clean, maintainable, and extensible code

                    Ideal for:
                    - Enterprises that want to restrict user record creation
                    - Developers seeking a centralized override
        Changelog:
        v1.0.0 - Initial release: disables 'Create' and 'Create and Edit' globally in many2one fields.
    """,

    'author': "Hari",
    'category': 'Customizations',
    'version': '1.0.0',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'disable_global_many2one_create_and_edit_options/static/src/js/disable_create_edit.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}

