import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api
import auth

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
        with patch.object(api.mailer, "send_test_mode_email") as send:
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


if __name__ == "__main__":
    unittest.main()
