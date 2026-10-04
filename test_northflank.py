import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import api

SECRET = {"JWT_SECRET": "test-secret-" + "x" * 32}

class NorthflankRoutes(unittest.TestCase):
    def test_aliases_use_existing_handlers_and_protect_user_data(self):
        with patch.object(api, "PUBLIC", True), patch.dict(os.environ, SECRET):
            client = TestClient(api.app)
            headers = {"Authorization": "Bearer " + api.auth.create_token(1)}
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            for route in ("/profile", "/requests", "/api/profile", "/api/requests", "/jobs/missing"):
                self.assertEqual(client.get(route).status_code, 401)
            self.assertEqual(client.post("/chat", json={}).status_code, 401)
            # The old anonymous visitor token is no longer accepted.
            self.assertEqual(client.get("/profile", headers={"Authorization": "Bearer " + "a" * 64}).status_code, 401)
            with patch.object(api, "visitor_busy", return_value=False), \
                    patch.object(api.db, "get_user_profile", return_value={"name": "N", "needs": ["Captions"]}), \
                    patch.object(api.db, "save_user_needs") as save:
                self.assertEqual(client.post("/profile", headers=headers, json={"needs": ["Captions"]}).status_code, 200)
                save.assert_called_once_with(1, ["Captions"])
                self.assertEqual(client.get("/api/profile", headers=headers).json()["needs"], ["Captions"])
            with patch.object(api.db, "list_requests", return_value=[]) as listed:
                self.assertEqual(client.get("/requests", headers=headers).json(), [])
                listed.assert_called_once_with(1)
            with patch.object(api, "analyze", return_value={"id":"job"}) as analyze:
                self.assertEqual(client.post("/chat", headers=headers, json={"url":"https://example.org/event"}).status_code, 202)
                self.assertEqual(str(analyze.call_args.args[0].url), "https://example.org/event")
            with patch.object(api, "message", return_value={"id":"job"}) as message:
                self.assertEqual(client.post("/chat", headers=headers, json={"session_id":"session", "message":"Draft only"}).status_code, 202)
                self.assertEqual(message.call_args.args[0], "session")
            self.assertEqual(client.post("/chat", headers=headers, json={}).status_code, 422)
            self.assertEqual(client.post("/requests/missing/check", headers=headers).status_code, 422)
            with patch.object(api.db, "get_request", return_value=None) as get:
                self.assertEqual(client.post("/requests/999/check", headers=headers).status_code, 404)
                get.assert_called_once_with(1, 999)

if __name__ == "__main__": unittest.main()
