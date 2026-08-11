from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Remove the obsolete payroll-page override when it exists."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    view = env.ref(
        "harleys_customization.hr_employee_form_payroll_page_inherit",
        raise_if_not_found=False,
    )
    if view:
        view.unlink()
