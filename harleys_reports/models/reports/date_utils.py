from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.exceptions import ValidationError


def date_boundary(env, value, end=False):
    try:
        parsed = fields.Date.to_date(value)
    except (TypeError, ValueError):
        parsed = None
    if not parsed:
        raise ValidationError("Invalid date value.")
    if end:
        parsed += timedelta(days=1)
    user_tz = ZoneInfo(env.user.tz or "UTC")
    local = datetime.combine(parsed, time.min, tzinfo=user_tz)
    return local.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
