import logging
import time

from odoo import api, models
from odoo.http import request, root, SessionExpiredException

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _check_session_expiry(cls):
        session = request.session
        if not session.uid:
            return

        user = request.env(user=session.uid).user
        timeout = user._get_lock_timeout_inactivity()

        if not timeout:
            return

        now = time.time()

        if "inactivity_start" not in session:
            session["inactivity_start"] = now
            root.session_store.save(session)
            return

        inactive_since = session.get("inactivity_start", now)
        inactivity_duration = now - inactive_since

        if inactivity_duration >= timeout:
            session.pop("inactivity_start", None)
            session.pop("identity-check-next", None)
            root.session_store.save(session)
            raise SessionExpiredException(
                f"User {session.uid} session expired due to inactivity after {inactivity_duration:.1f}s"
            )

    @classmethod
    def _reset_inactivity_timer(cls):
        session = request.session
        if session.uid:
            session["inactivity_start"] = time.time()
            root.session_store.save(session)

    @classmethod
    def _authenticate(cls, endpoint):
        cls._reset_inactivity_timer()
        cls._check_session_expiry()
        super()._authenticate(endpoint)

    def _set_session_inactivity(self, session, inactivity_period=0, force=False):
        pass
