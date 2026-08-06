import json
import time

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import AccessDenied
from odoo.http import SessionExpiredException


@tagged("hr_shared_login_binding")
class TestInactivityTimeout(TransactionCase):
    """Test inactivity timeout behavior for all users."""

    def setUp(self):
        super().setUp()
        self.shared_user = self.env["res.users"].create(
            {
                "name": "Shared User",
                "login": "shared",
                "is_shared_login": True,
            }
        )
        self.normal_user = self.env["res.users"].create(
            {
                "name": "Normal User",
                "login": "normal",
            }
        )
        self.admin_user = self.env.ref("base.user_admin")
        self.shared_group = self.env["res.groups"].create(
            {
                "name": "Shared Group",
                "user_ids": [(4, self.shared_user.id)],
                "lock_timeout_inactivity": 15,  # 15 minutes
            }
        )
        self.normal_group = self.env["res.groups"].create(
            {
                "name": "Normal Group",
                "user_ids": [(4, self.normal_user.id)],
                "lock_timeout_inactivity": 15,
            }
        )
        self.shared_user.group_ids = [(4, self.shared_group.id)]
        self.normal_user.group_ids = [(4, self.normal_group.id)]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def authenticate(self, login, password):
        return self.env["res.users"].authenticate(
            {"login": login, "password": password, "type": "password"},
            {"interactive": True, "base_location": "http://localhost:8069"},
        )

    def set_session_last_activity(self, session_id, timestamp):
        session = self.env["ir.http"].session_store.get(session_id)
        session["last_activity"] = timestamp
        self.env["ir.http"].session_store.save(session)

    def rpc(self, session_id, model, method, args, kwargs=None):
        kwargs = kwargs or {}
        session = self.env["ir.http"].session_store.get(session_id)
        env = self.env(user=session.uid, context=session.context)
        try:
            result = getattr(env[model], method)(*args, **kwargs)
            return {"result": result}
        except SessionExpiredException as e:
            return {"error": {"data": {"name": "odoo.http.SessionExpiredException"}, "message": str(e)}}
        except Exception as e:
            return {"error": {"data": {"name": type(e).__name__}, "message": str(e)}}

    # -------------------------------------------------------------------------
    # Scenario 1: Idle timeout
    # -------------------------------------------------------------------------

    def test_shared_user_idle_timeout_rejected(self):
        """Shared user idle beyond timeout should get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_shared_user_active_not_rejected(self):
        """Active shared user should NOT get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 5 * 60)  # 5 min ago

        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])

        self.assertIn("name", result.get("result", [{}])[0])

    def test_normal_user_idle_timeout_rejected(self):
        """Normal user idle beyond timeout should also get SessionExpiredException."""
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        result = self.rpc(session_id, "res.users", "read", [self.normal_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_normal_user_active_not_rejected(self):
        """Active normal user should NOT get SessionExpiredException."""
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 5 * 60)  # 5 min ago

        result = self.rpc(session_id, "res.users", "read", [self.normal_user.id], ["name"])

        self.assertIn("name", result.get("result", [{}])[0])

    def test_admin_user_idle_timeout_rejected(self):
        """Admin user idle beyond timeout should also get SessionExpiredException."""
        auth = self.authenticate(self.admin_user.login, self.admin_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        result = self.rpc(session_id, "res.users", "read", [self.admin_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    # -------------------------------------------------------------------------
    # Scenario 2: Background activity
    # -------------------------------------------------------------------------

    def test_authenticated_request_resets_last_activity(self):
        """Any authenticated request should update last_activity."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        old_time = time.time() - 60
        self.set_session_last_activity(session_id, old_time)

        self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])

        session = self.env["ir.http"].session_store.get(session_id)
        self.assertGreater(session.get("last_activity", 0), old_time)

    def test_bus_longpolling_style_request_resets_activity(self):
        """Bus/longpolling-style authenticated requests also reset last_activity."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        old_time = time.time() - 60
        self.set_session_last_activity(session_id, old_time)

        # Simulate a bus-style read request (any authenticated call works the same)
        self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["login"])

        session = self.env["ir.http"].session_store.get(session_id)
        self.assertGreater(session.get("last_activity", 0), old_time)

    # -------------------------------------------------------------------------
    # Scenario 3: Multi-tab (server-side)
    # -------------------------------------------------------------------------

    def test_multi_tab_same_session_shared(self):
        """Two requests with same session_id: activity in one keeps both alive."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        # Simulate "tab 2" making a request just before timeout
        self.set_session_last_activity(session_id, time.time() - 5 * 60)  # 5 min ago

        # Now "tab 1" makes a request - should succeed because last_activity was reset
        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])
        self.assertIn("name", result.get("result", [{}])[0])

    # -------------------------------------------------------------------------
    # Scenario 4: Non-browser clients (JSON-RPC style)
    # -------------------------------------------------------------------------

    def test_json_rpc_expired_shared_session(self):
        """JSON-RPC call with expired shared session should get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])

        # Server must enforce timeout even without JavaScript
        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_xml_rpc_style_expired_shared_session(self):
        """XML-RPC style call with expired shared session should be rejected."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)  # 20 min ago

        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["login"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    # -------------------------------------------------------------------------
    # Edge cases
    # -------------------------------------------------------------------------

    def test_shared_user_no_timeout_configured(self):
        """Shared user with no lock_timeout_inactivity should never expire."""
        self.shared_group.lock_timeout_inactivity = False
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 24 * 60 * 60)  # 24 hours

        result = self.rpc(session_id, "res.users", "read", [self.shared_user.id], ["name"])
        self.assertIn("name", result.get("result", [{}])[0])

    def test_normal_user_no_timeout_configured(self):
        """Normal user with no lock_timeout_inactivity should never expire."""
        self.normal_group.lock_timeout_inactivity = False
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 24 * 60 * 60)  # 24 hours

        result = self.rpc(session_id, "res.users", "read", [self.normal_user.id], ["name"])
        self.assertIn("name", result.get("result", [{}])[0])

    def test_first_request_initializes_last_activity(self):
        """First authenticated request after login should set last_activity."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        session = self.env["ir.http"].session_store.get(session_id)
        self.assertIn("last_activity", session)
        self.assertAlmostEqual(session["last_activity"], time.time(), delta=60)

    def test_normal_user_effective_timeout_is_from_group(self):
        """Normal user should get lock_timeout_inactivity from their group."""
        timeout = self.env["ir.http"]._get_effective_timeout(self.normal_user)
        self.assertEqual(timeout, 15 * 60)

    def test_shared_user_effective_timeout_is_from_group(self):
        """Shared user should get lock_timeout_inactivity from their group."""
        timeout = self.env["ir.http"]._get_effective_timeout(self.shared_user)
        self.assertEqual(timeout, 15 * 60)

    def test_user_without_group_timeout_is_none(self):
        """User with no groups and no timeout should get None."""
        orphan = self.env["res.users"].create({"name": "Orphan", "login": "orphan"})
        timeout = self.env["ir.http"]._get_effective_timeout(orphan)
        self.assertIsNone(timeout)
