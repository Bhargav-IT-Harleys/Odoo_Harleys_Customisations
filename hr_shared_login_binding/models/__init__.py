from . import res_users
from . import employee_attribution_mixin
# Disabled in favour of the mail.thread-level wrapper below - see
# message_attribution.py's module docstring. Kept importable (uncomment) as
# a fallback/reference if the wrapper approach ever needs to be reverted.
# from . import attribution_targets
from . import message_attribution
