import json
import time
import xmlrpc.client

import odoo
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.http import SessionExpiredException


@tagged("hr_shared_login_binding")
class TestInactivityTimeout(HttpCase):
    """Test inactivity timeout behavior for all users."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.shared_user = new_test_user(
            cls.env, "shared", groups="base.group_user", is_shared_login=True
        )
        cls.normal_user = new_test_user(
            cls.env, "normal", groups="base.group_user"
        )
        cls.admin_user = cls.env.ref("base.user_admin")
        cls.admin_user.write({"password": "admin"})

        cls.shared_group = cls.env["res.groups"].create(
            {
                "name": "Shared Group",
                "user_ids": [(4, cls.shared_user.id)],
                "lock_timeout_inactivity": 15,
            }
        )
        cls.normal_group = cls.env["res.groups"].create(
            {
                "name": "Normal Group",
                "user_ids": [(4, cls.normal_user.id)],
                "lock_timeout_inactivity": 15,
            }
        )
        cls.admin_group = cls.env["res.groups"].create(
            {
                "name": "Admin Timeout Group",
                "user_ids": [(4, cls.admin_user.id)],
                "lock_timeout_inactivity": 15,
            }
        )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def set_session_last_activity(self, session_id, timestamp):
        session = odoo.http.root.session_store.get(session_id)
        session["last_activity"] = timestamp
        odoo.http.root.session_store.save(session)

    def rpc(self, model, method, *args, **kwargs):
        return self.url_open(
            "/web/dataset/call_kw",
            json={
                "params": {
                    "model": model,
                    "method": method,
                    "args": args,
                    "kwargs": kwargs,
                }
            },
        ).json()

    def xmlrpc(self, model, method, *args, **kwargs):
        password = self.shared_user.login + "x" * (8 - len(self.shared_user.login))
        body = xmlrpc.client.dumps(
            (
                self.env.cr.dbname,
                self.session.uid,
                password,
                model,
                method,
                list(args),
                kwargs,
            ),
            "execute_kw",
        )
        response = self.url_open(
            "/xmlrpc/2/object",
            data=body,
            headers={"Content-Type": "text/xml"},
            allow_redirects=False,
        )
        if response.status_code == 303:
            return {"redirect": response.headers.get("Location")}
        try:
            return xmlrpc.client.loads(response.content)
        except xmlrpc.client.Fault as e:
            return {"fault": str(e)}

    # -------------------------------------------------------------------------
    # Scenario 1: Idle timeout
    # -------------------------------------------------------------------------

    def test_shared_user_idle_timeout_rejected(self):
        """Shared user idle beyond timeout should get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)

        result = self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_shared_user_active_not_rejected(self):
        """Active shared user should NOT get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 5 * 60)

        result = self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        self.assertIn("result", result)

    def test_normal_user_idle_timeout_rejected(self):
        """Normal user idle beyond timeout should also get SessionExpiredException."""
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)

        result = self.rpc("res.users", "read", [self.normal_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_normal_user_active_not_rejected(self):
        """Active normal user should NOT get SessionExpiredException."""
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 5 * 60)

        result = self.rpc("res.users", "read", [self.normal_user.id], ["name"])

        self.assertIn("result", result)

    def test_admin_user_idle_timeout_rejected(self):
        """Admin user idle beyond timeout should also get SessionExpiredException."""
        auth = self.authenticate(self.admin_user.login, self.admin_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)

        result = self.rpc("res.users", "read", [self.admin_user.id], ["name"])

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

        self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        session = odoo.http.root.session_store.get(session_id)
        self.assertGreater(session.get("last_activity", 0), old_time)

    def test_bus_request_does_not_reset_last_activity(self):
        """Bus requests do not reset last_activity."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        old_time = time.time() - 60
        self.set_session_last_activity(session_id, old_time)

        self.url_open("/bus/get_model_definitions", json={"model_names_to_fetch": "[]"})

        session = odoo.http.root.session_store.get(session_id)
        self.assertLessEqual(session.get("last_activity", 0), old_time + 1)

    # -------------------------------------------------------------------------
    # Scenario 3: Multi-tab (server-side)
    # -------------------------------------------------------------------------

    def test_multi_tab_same_session_shared(self):
        """Two requests with same session: activity in one keeps both alive."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 5 * 60)

        self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        result = self.rpc("res.users", "read", [self.shared_user.id], ["name"])
        self.assertIn("result", result)

    # -------------------------------------------------------------------------
    # Scenario 4: Non-browser clients
    # -------------------------------------------------------------------------

    def test_json_rpc_expired_shared_session(self):
        """JSON-RPC call with expired shared session should get SessionExpiredException."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)

        result = self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        self.assertEqual(
            result.get("error", {}).get("data", {}).get("name"),
            "odoo.http.SessionExpiredException",
        )

    def test_xml_rpc_style_expired_shared_session(self):
        """XML-RPC call with expired shared session is redirected to login."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 20 * 60)

        result = self.xmlrpc("res.users", "read", [self.shared_user.id], ["name"])

        self.assertIn("redirect", result)
        self.assertIn("/web/login", result["redirect"])

    # -------------------------------------------------------------------------
    # Edge cases
    # -------------------------------------------------------------------------

    def test_shared_user_no_timeout_configured(self):
        """Shared user with no lock_timeout_inactivity should never expire."""
        self.shared_group.lock_timeout_inactivity = False
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 24 * 60 * 60)

        result = self.rpc("res.users", "read", [self.shared_user.id], ["name"])
        self.assertIn("result", result)

    def test_normal_user_no_timeout_configured(self):
        """Normal user with no lock_timeout_inactivity should never expire."""
        self.normal_group.lock_timeout_inactivity = False
        auth = self.authenticate(self.normal_user.login, self.normal_user.login)
        session_id = auth.sid
        self.set_session_last_activity(session_id, time.time() - 24 * 60 * 60)

        result = self.rpc("res.users", "read", [self.normal_user.id], ["name"])
        self.assertIn("result", result)

    def test_first_request_initializes_last_activity(self):
        """First authenticated request after login should set last_activity."""
        auth = self.authenticate(self.shared_user.login, self.shared_user.login)
        session_id = auth.sid

        self.rpc("res.users", "read", [self.shared_user.id], ["name"])

        session = odoo.http.root.session_store.get(session_id)
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
