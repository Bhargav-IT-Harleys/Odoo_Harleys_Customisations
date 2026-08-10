import logging
import time

from odoo import api, models
from odoo.http import request, SessionExpiredException

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_effective_timeout(cls, user):
        """Return the inactivity timeout in seconds for this user, or None.

        Applies to ALL users, not just shared-login users.
        """
        return user._get_lock_timeout_inactivity()

    @classmethod
    def _check_session_expiry(cls):
        session = request.session
        if not session.uid:
            return

        try:
            user = request.env(user=session.uid).user
        except Exception as e:
            _logger.debug(
                "_check_session_expiry: skipped for session uid=%s: %s",
                session.uid,
                e,
            )
            return

        timeout = cls._get_effective_timeout(user)
        if not timeout:
            return

        now = time.time()
        last_activity = session.get("last_activity")

        if last_activity is None:
            session["last_activity"] = now
            return

        inactivity_duration = now - last_activity

        if inactivity_duration >= timeout:
            session.pop("last_activity", None)
            _logger.info(
                "[hr_inactivity] user %s session expired after %.1fs inactivity",
                user.id,
                inactivity_duration,
            )
            raise SessionExpiredException(
                f"User {session.uid} session expired due to inactivity after {inactivity_duration:.1f}s"
            )

    @classmethod
    def _update_last_activity(cls):
        session = request.session
        if not session.uid:
            return
        path = request.httprequest.path
        if path.startswith("/bus/") or path == "/websocket" or path == "/web/session/logout":
            return
        session["last_activity"] = time.time()

    @classmethod
    def _authenticate(cls, endpoint):
        cls._check_session_expiry()
        result = super()._authenticate(endpoint)
        cls._update_last_activity()
        return result

    @classmethod
    def _must_check_identity(cls, session=None, inactivity_period=0, force=False):
        """Disable auth_timeout's check-identity flow for ALL users."""
        return False

    def _set_session_inactivity(self, session, inactivity_period=0, force=False):
        """Intentionally no-op.

        auth_timeout uses this to record the inactivity period on the session
        and later trigger its check-identity wizard.  Our module replaces that
        flow with server-side ``_check_session_expiry``, so we suppress the
        stock identity-check here.
        """
        pass

    def _session_info_common_hr_inactivity(self, session_info):
        """Add custom inactivity timeout metadata, replacing auth_timeout's."""
        if not self.env.user._is_public() and (timeout := self.env.user._get_lock_timeout_inactivity()):
            session_info["hr_inactivity_timeout"] = timeout
        session_info.pop("lock_timeout_inactivity", None)
        return session_info

    def session_info(self):
        session_info = super().session_info()
        return self._session_info_common_hr_inactivity(session_info)
