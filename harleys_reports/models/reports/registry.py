from odoo.exceptions import ValidationError


REPORTS = {}


def register_report(provider_class):
    if not provider_class.key or provider_class.key in REPORTS:
        raise ValueError(f"Invalid or duplicate report key: {provider_class.key}")
    REPORTS[provider_class.key] = provider_class
    return provider_class


def get_report(report_key):
    if not isinstance(report_key, str) or report_key not in REPORTS:
        raise ValidationError("Unknown report.")
    return REPORTS[report_key]
