import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock, Mock

import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api
import auth
import db
import psycopg
import ast
from pathlib import Path

# A network/database access attempt is a test failure, not an optional service.
def setUpModule():
    global CONNECTION_GUARD
    CONNECTION_GUARD = patch("psycopg.connect", side_effect=AssertionError("Live PostgreSQL is forbidden in these tests"))
    CONNECTION_GUARD.start()


def tearDownModule():
    CONNECTION_GUARD.stop()


SECRET = {"JWT_SECRET": "test-secret-" + "x" * 32}


class Tokens(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, SECRET)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_token_round_trip(self):
        self.assertEqual(auth.user_from_header("Bearer " + auth.create_token(42)), 42)

    def test_rejects_missing_tampered_and_expired_tokens(self):
        expired = jwt.encode({"user_id": 1, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SECRET["JWT_SECRET"], algorithm="HS256")
        forged = jwt.encode({"user_id": 1, "exp": datetime.now(timezone.utc) + timedelta(days=1)}, "another-secret-" + "y" * 32, algorithm="HS256")
        unsigned = jwt.encode({"user_id": 1, "exp": datetime.now(timezone.utc) + timedelta(days=1)}, None, algorithm="none")
        for header in (None, "", "Token abc", "Bearer " + expired, "Bearer " + forged, "Bearer " + unsigned):
            with self.assertRaises(HTTPException) as caught:
                auth.user_from_header(header)
            self.assertEqual(caught.exception.status_code, 401)

    def test_token_lasts_seven_days(self):
        claims = jwt.decode(auth.create_token(1), SECRET["JWT_SECRET"], algorithms=["HS256"])
        self.assertAlmostEqual(claims["exp"] - claims["iat"], 7 * 24 * 3600, delta=5)

    def test_missing_or_short_secret_is_an_error(self):
        with patch.dict(os.environ, {"JWT_SECRET": "short"}):
            with self.assertRaises(RuntimeError):
                auth.create_token(1)

    def test_otp_is_six_digits_and_stored_hashed(self):
        code = auth.new_otp()
        self.assertRegex(code, r"^\d{6}$")
        self.assertNotIn(code, auth.hash_otp(code))
        self.assertEqual(auth.hash_otp(code), auth.hash_otp(code))


class Endpoints(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ, SECRET)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(api.app)

    def register(self, **changes):
        body = {"name": "Norah", "email": "Norah@Example.com", "preferred_language": "ar", "consent": True, **changes}
        return self.client.post("/auth/register", json=body)

    def test_register_requires_consent_and_known_language(self):
        with patch.object(api.db, "create_user") as create:
            self.assertEqual(self.register(consent=False).status_code, 422)
            self.assertEqual(self.register(consent="yes").status_code, 422)
            self.assertEqual(self.register(preferred_language="fr").status_code, 422)
            self.assertEqual(self.register(email="not-an-email").status_code, 422)
            create.assert_not_called()

    def test_register_lowercases_email_and_rejects_duplicates(self):
        with patch.object(api.db, "create_user", return_value=5) as create:
            self.assertEqual(self.register().json(), {"user_id": 5})
            create.assert_called_once_with("Norah", "norah@example.com", "ar")
        with patch.object(api.db, "create_user", return_value=None):
            self.assertEqual(self.register().status_code, 409)

    def test_send_otp_gives_same_answer_for_unknown_email(self):
        with patch.object(api.mailer, "send_otp_email") as send:
            with patch.object(api.db, "store_otp", return_value=None):
                unknown = self.client.post("/auth/send-otp", json={"email": "nobody@example.com"})
            send.assert_not_called()
            with patch.object(api.db, "store_otp", return_value="en") as store:
                known = self.client.post("/auth/send-otp", json={"email": "Norah@Example.com"})
            self.assertEqual(unknown.json(), known.json())
            self.assertEqual(store.call_args.args[0], "norah@example.com")
            code = send.call_args.args[2].split(": ")[1][:6]
            self.assertEqual(store.call_args.args[1], auth.hash_otp(code))

    def test_verify_otp_returns_token_for_that_user(self):
        with patch.object(api.db, "verify_otp", return_value=None):
            self.assertEqual(self.client.post("/auth/verify-otp", json={"email": "n@example.com", "code": "123456"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/verify-otp", json={"email": "n@example.com", "code": "12345"}).status_code, 422)
        with patch.object(api.db, "verify_otp", return_value=9):
            token = self.client.post("/api/auth/verify-otp", json={"email": "n@example.com", "code": "123456"}).json()["access_token"]
        self.assertEqual(auth.user_from_header("Bearer " + token), 9)

    def test_user_id_comes_only_from_the_token(self):
        headers = {"Authorization": "Bearer " + auth.create_token(3)}
        with patch.object(api.db, "list_requests", return_value=[]) as listed:
            self.client.get("/api/requests?user_id=4", headers=headers)
            listed.assert_called_once_with(3)

    def test_delete_account_removes_only_the_token_user(self):
        api.sessions.update(mine=object(), theirs=object())
        api.session_context.update(mine={"owner": "1"}, theirs={"owner": "2"})
        api.jobs.update(j_mine={"id": "j_mine", "session_id": "mine", "status": "completed"},
                        j_theirs={"id": "j_theirs", "session_id": "theirs", "status": "completed"})
        def cleanup():
            for store in (api.sessions, api.session_context):
                store.pop("mine", None); store.pop("theirs", None)
            api.jobs.pop("j_mine", None); api.jobs.pop("j_theirs", None)
        self.addCleanup(cleanup)
        headers = {"Authorization": "Bearer " + auth.create_token(1)}
        with patch.object(api.db, "delete_user", return_value=True) as delete:
            self.assertEqual(self.client.delete("/api/account?user_id=2", headers=headers).status_code, 204)
            delete.assert_called_once_with(1)
        self.assertNotIn("mine", api.sessions)
        self.assertNotIn("j_mine", api.jobs)
        self.assertIn("theirs", api.sessions)
        self.assertIn("j_theirs", api.jobs)
        self.assertEqual(self.client.delete("/api/account").status_code, 401)

    def test_users_cannot_reach_each_others_sessions(self):
        api.sessions["s1"] = object()
        api.session_context["s1"] = {"owner": "1"}
        api.jobs["j1"] = {"id": "j1", "session_id": "s1", "status": "completed"}
        self.addCleanup(lambda: [api.sessions.pop("s1"), api.session_context.pop("s1"), api.jobs.pop("j1")])
        own = self.client.get("/api/jobs/j1", headers={"Authorization": "Bearer " + auth.create_token(1)})
        other = self.client.get("/api/jobs/j1", headers={"Authorization": "Bearer " + auth.create_token(2)})
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)


class StorageContracts(unittest.TestCase):
    def test_public_ids_remain_strings_and_invalid_ids_do_not_query(self):
        self.assertEqual(db.public_request_id(1), "REQ-001")
        self.assertEqual(db.public_request_id(1024), "REQ-1024")
        self.assertEqual(db.internal_request_id("REQ-001"), 1)
        with patch.object(db, "get_connection") as connection:
            self.assertIsNone(db.get_request(7, "not-an-id"))
            self.assertIsNone(db.update_request(7, "not-an-id", {}))
            connection.assert_not_called()

    def test_serialized_requests_preserve_frontend_contract_and_owner_filter(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [{
            "request_id": 12, "event_name": "Academic Expo", "event_url": "https://example.com/event",
            "organizer_email": "organizer@example.com", "email_subject": "Request [Accessly abc]",
            "overall_status": "PENDING", "need_name": "Captions", "status": "NOT APPLICABLE",
        }]
        result = db._fetch_requests(conn, 7, 12)
        self.assertEqual(result[0]["request_id"], "REQ-012")
        self.assertEqual(result[0]["accommodations"], {"Captions": "NOT APPLICABLE"})
        query, params = conn.execute.call_args.args
        self.assertIn("r.user_id = %s", query)
        self.assertEqual(params, [7, 12])

    def test_unowned_request_cannot_be_updated(self):
        conn = MagicMock()
        conn.__enter__().execute.return_value.fetchone.return_value = None
        with patch.object(db, "get_connection", return_value=conn):
            self.assertIsNone(db.update_request(2, "REQ-003", {"Captions": "CONFIRMED"}, "CONFIRMED"))
        self.assertEqual(conn.__enter__().execute.call_count, 1)
        conn.__enter__().cursor.assert_not_called()

    def test_otp_attempt_limit_and_single_use_clear_the_code(self):
        for attempts, fresh, supplied, clears, expected in [
            (0, True, "correct", True, 9), (4, True, "wrong", True, None),
            (0, False, "correct", True, None), (0, True, "wrong", False, None),
        ]:
            with self.subTest(attempts=attempts, fresh=fresh, supplied=supplied):
                conn = MagicMock()
                cursor = conn.__enter__().execute.return_value
                cursor.fetchone.return_value = {"user_id": 9, "otp_code": "correct", "otp_attempts": attempts, "fresh": fresh}
                with patch.object(db, "get_connection", return_value=conn):
                    self.assertEqual(db.verify_otp("a@example.com", supplied), expected)
                statements = [call.args[0] for call in conn.__enter__().execute.call_args_list]
                self.assertIn("FOR UPDATE", statements[0])
                self.assertEqual("otp_code = NULL" in statements[-1], clears)

    def test_removing_needs_is_soft_delete_and_custom_needs_are_marked(self):
        conn = MagicMock()
        with patch.object(db, "get_connection", return_value=conn):
            db.save_user_needs(4, ["Captions", "Other: quiet space"])
        self.assertIn("is_active = FALSE", conn.__enter__().execute.call_args.args[0])
        params = conn.__enter__().cursor().executemany.call_args.args[1]
        self.assertEqual(params, [(4, "Captions", False), (4, "Other: quiet space", True)])

    def test_schema_is_not_executed_on_api_import_or_health(self):
        with patch.object(db, "get_connection", side_effect=AssertionError("No DB for health")):
            self.assertEqual(TestClient(api.app).get("/api/health").json(), {"status": "ok"})


class AuthenticatedWorkflow(unittest.TestCase):
    def setUp(self):
        secret = patch.dict(os.environ, SECRET)
        secret.start(); self.addCleanup(secret.stop)
        self.client = TestClient(api.app)
        self.headers = {"Authorization": "Bearer " + auth.create_token(7)}

    def test_profile_and_request_aliases_use_token_owner(self):
        profile = {"name": "Noura", "preferred_language": "en", "needs": ["Captions"]}
        with patch.object(db, "get_user_profile", return_value=profile) as get, patch.object(db, "save_user_needs") as save:
            for route in ("/profile", "/api/profile"):
                self.assertEqual(self.client.get(route, headers=self.headers).json(), profile)
                self.assertEqual(self.client.get(route).status_code, 401)
            response = self.client.post("/api/profile", headers=self.headers, json={"needs": [" Captions ", "Captions"]})
            self.assertEqual(response.status_code, 200)
            save.assert_called_once_with(7, ["Captions"])
            self.assertTrue(all(call.args == (7,) for call in get.call_args_list))
        with patch.object(db, "list_requests", return_value=[]) as listed:
            self.assertEqual(self.client.get("/requests", headers=self.headers).json(), [])
            listed.assert_called_once_with(7)

    def test_string_request_check_preserves_existing_prompt_and_needs(self):
        record = {"request_id": "REQ-001", "event_url": "https://example.com/event", "accommodations": {"Captions": "PENDING"}}
        with patch.object(db, "list_requests", return_value=[record]), patch.object(api, "submit", return_value={"id": "j", "session_id": "s", "status": "processing", "response": ""}) as submit:
            response = self.client.post("/api/requests/REQ-001/check", headers=self.headers)
            self.assertEqual(response.status_code, 202)
            session_id, message = submit.call_args.args
            self.addCleanup(lambda: api.sessions.pop(session_id, None))
            self.addCleanup(lambda: api.session_context.pop(session_id, None))
            self.assertEqual(message, "Check reply for REQ-001")
            self.assertEqual(api.session_context[session_id]["owner"], "7")
            self.assertEqual(api.session_context[session_id]["needs"], ["Captions"])

    def test_event_job_contract_and_background_owner_are_preserved(self):
        profile = {"name": "Noura", "needs": ["Captions"]}
        queued = []
        fake_agent = Mock(return_value="Verified event report")
        runtime_namespace = {"agent": fake_agent}
        formatted = {"schema_version": 1, "presentation_status": "ready", "message": "Result", "event": None, "accessibility_results": [], "recommended_action": None, "draft": None, "requests": []}
        def record_queue(*args): queued.append(args)
        try:
            with patch.object(api, "PUBLIC", False), patch.object(db, "get_user_profile", return_value=profile), patch.object(db, "list_requests", return_value=[]), patch.object(api, "reserve_action"), patch.object(api.worker, "submit", side_effect=record_queue), patch.object(api.runpy, "run_path", return_value=runtime_namespace), patch.object(api, "configure_agent") as configure, patch.object(api, "authorize_approval"), patch.object(api, "format_result", return_value=formatted):
                response = self.client.post("/api/events", headers=self.headers, json={"url": "https://example.com/event"})
                self.assertEqual(response.status_code, 202)
                job = response.json()
                self.assertEqual(set(job), {"id", "session_id", "status", "response"})
                self.assertEqual(job["status"], "processing")
                # Run the queued copied context on this thread without model/browser work.
                callback, *args = queued.pop(0)
                callback(*args)
                configure.assert_called_once_with(runtime_namespace, api.session_context[job["session_id"]])
                fake_agent.assert_called_once_with("Check this event: https://example.com/event")
                polled = self.client.get("/api/jobs/" + job["id"], headers=self.headers).json()
                self.assertEqual(polled["status"], "completed")
                self.assertEqual(polled["result"], formatted)
        finally:
            if 'job' in locals():
                api.jobs.pop(job["id"], None)
                api.sessions.pop(job["session_id"], None)
                api.session_context.pop(job["session_id"], None)

    def test_format_retry_preserves_result_schema_without_agent_call(self):
        api.sessions["format-session"] = Mock()
        api.session_context["format-session"] = {"owner": "7", "needs": ["Captions"], "url": "https://example.com", "result": None}
        api.jobs["format-job"] = {"id": "format-job", "session_id": "format-session", "status": "completed", "response": "Report"}
        self.addCleanup(lambda: api.sessions.pop("format-session", None))
        self.addCleanup(lambda: api.session_context.pop("format-session", None))
        self.addCleanup(lambda: api.jobs.pop("format-job", None))
        result = {"schema_version": 1, "presentation_status": "ready", "message": "Result", "event": None, "accessibility_results": [], "recommended_action": None, "draft": None, "requests": []}
        def inline(callback, *args): callback(*args)
        with patch.object(api.worker, "submit", side_effect=inline), patch.object(api, "reserve_action"), patch.object(api, "format_result", return_value=result), patch.object(db, "list_requests", return_value=[]):
            response = self.client.post("/api/jobs/format-job/presentation", headers=self.headers)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["result"], result)
            api.sessions["format-session"].assert_not_called()

    def test_agent_binding_uses_verified_owner_without_browser_or_database(self):
        import deployment_runtime as runtime
        namespace = {}
        exec("def load_user_profile(): return {}", namespace)
        with patch.object(runtime, "PUBLIC", False):
            runtime.configure_agent(namespace, {"owner": "7"})
        self.assertEqual(namespace["load_user_profile"].__globals__["USER_ID"], 7)
        self.assertNotIn("PROFILE_FILE", namespace)

    def test_legacy_random_visitor_token_is_rejected_without_database_access(self):
        self.assertEqual(self.client.get("/api/profile", headers={"Authorization": "Bearer " + "a" * 64}).status_code, 401)

    def test_agent_persistence_adapters_keep_tool_signatures_and_request_shapes(self):
        tree = ast.parse(Path("main.py").read_text())
        names = {"current_user_id", "load_user_profile", "load_requests", "save_requests", "create_request_record", "update_request_status"}
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        for node in functions: node.decorator_list = []
        namespace = {"db": db, "USER_ID": 7}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "main.py", "exec"), namespace)
        record = {"request_id": "REQ-001", "status": "PENDING", "accommodations": {"Captions": "PENDING"}}
        with patch.object(db, "get_user_profile", return_value={"needs": ["Captions"]}), patch.object(db, "create_request", return_value=record) as create, patch.object(db, "update_request", return_value=record) as update:
            self.assertEqual(namespace["create_request_record"]("Expo", "https://example.com", "a@example.com", "Subject")["request"], record)
            create.assert_called_once_with(7, "Expo", "https://example.com", "a@example.com", "Subject")
            self.assertEqual(namespace["update_request_status"]("REQ-001", "PENDING", {"Captions": "PENDING"})["status"], "updated")
            update.assert_called_once_with(7, "REQ-001", {"Captions": "PENDING"}, "PENDING")


class OtpDelivery(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            **SECRET, "ACCESSLY_EMAIL": "sender@example.com",
            "ACCESSLY_EMAIL_APP_PASSWORD": "fake-app-password",
            "ACCESSLY_TEST_RECIPIENT": "test-inbox@example.com",
        })
        environment.start(); self.addCleanup(environment.stop)
        smtp = patch("mailer.smtplib.SMTP")
        self.smtp_factory = smtp.start(); self.addCleanup(smtp.stop)
        self.smtp = self.smtp_factory.return_value.__enter__.return_value
        self.client = TestClient(api.app)

    def test_create_account_otp_is_delivered_to_registration_email(self):
        with patch.object(db, "create_user", return_value=42), patch.object(db, "store_otp", return_value="en"), patch.object(api.mailer, "send_test_mode_email", side_effect=AssertionError("OTP must not use test delivery")):
            response = self.client.post("/api/auth/register", json={"name": "Test User", "email": "New.User@Example.com", "preferred_language": "en", "consent": True})
            self.assertEqual(response.status_code, 201)
            response = self.client.post("/api/auth/send-otp", json={"email": "New.User@Example.com"})
            self.assertEqual(response.status_code, 200)
        msg = self.smtp.send_message.call_args.args[0]
        self.assertEqual(msg["To"], "new.user@example.com")
        self.assertNotIn("TEST MODE", msg.get_content())
        self.assertNotIn("test-inbox@example.com", msg.as_string())
        self.smtp.login.assert_called_once_with("sender@example.com", "fake-app-password")
        self.smtp.starttls.assert_called_once()

    def test_login_otp_is_delivered_to_login_email_for_both_route_aliases(self):
        with patch.object(db, "store_otp", return_value="ar") as store:
            for route in ("/auth/send-otp", "/api/auth/send-otp"):
                self.smtp.reset_mock()
                response = self.client.post(route, json={"email": "Login.User@Example.com"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(store.call_args.args[0], "login.user@example.com")
                msg = self.smtp.send_message.call_args.args[0]
                self.assertEqual(msg["To"], "login.user@example.com")
                self.assertNotIn("test-inbox@example.com", msg.as_string())

    def test_test_recipient_is_not_required_for_otp(self):
        os.environ.pop("ACCESSLY_TEST_RECIPIENT", None)
        delivered = api.mailer.send_otp_email("user@example.com", "Your code", "123456")
        self.assertEqual(delivered, "user@example.com")
        self.assertEqual(self.smtp.send_message.call_args.args[0]["To"], "user@example.com")

    def test_empty_recipient_does_not_fall_back_to_test_inbox(self):
        with self.assertRaises(ValueError):
            api.mailer.send_otp_email(" ", "Your code", "123456")
        self.smtp.send_message.assert_not_called()

    def test_unknown_email_or_resend_cooldown_does_not_send_email(self):
        with patch.object(db, "store_otp", return_value=None):
            response = self.client.post("/api/auth/send-otp", json={"email": "user@example.com"})
            self.assertEqual(response.status_code, 200)
        self.smtp.send_message.assert_not_called()

    def test_accommodation_test_delivery_still_uses_test_recipient(self):
        actual = api.mailer.send_test_mode_email("organizer@example.com", "Accommodation", "Draft")
        self.assertEqual(actual, "test-inbox@example.com")
        msg = self.smtp.send_message.call_args.args[0]
        self.assertEqual(msg["To"], "test-inbox@example.com")
        self.assertIn("TEST MODE", msg.get_content())
        self.assertIn("organizer@example.com", msg.get_content())


if __name__ == "__main__":
    unittest.main()
