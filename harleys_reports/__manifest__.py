{
    "name": "Harley's Reports",
    "summary": "Read-only business reporting for Harley's",
    "version": "19.0.1.0.0",
    "category": "Customizations",
    "author": "Harley's",
    "license": "LGPL-3",
    "depends": ["base", "web", "stock"],
    "data": [
        "security/reports_security.xml",
        "views/reports_actions.xml",
        "views/cost_comparison_actions.xml",
        "views/download_history_actions.xml",
        "views/reports_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "harleys_reports/static/src/common/**/*",
            "harleys_reports/static/src/reports/**/*",
            "harleys_reports/static/src/cost_comparison/**/*",
            "harleys_reports/static/src/download_history/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
