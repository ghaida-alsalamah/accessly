import runpy
import smtplib
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import db

MAIN = runpy.run_path(str(Path(__file__).resolve().parent / "main.py"))
# run_path returns a copy; the functions read their globals from here.
GLOBALS = MAIN["notify_user_of_status_changes"].__globals__


def fake_notify(rows):
    """Stand-in for db.notify_status_changes that feeds `rows` to the send callback."""
    def notify(request_id, send):
        if not rows:
            return 0
        return len(rows) if send("user@secret.example", "ar", "Expo", rows) else 0
    return notify


class StatusEmail(unittest.TestCase):
    def test_arabic_email_translates_statuses(self):
        subject, body = MAIN["build_status_email"]("ar", "Expo", [("ASL", "CONFIRMED"), ("Parking", "MORE INFORMATION NEEDED")])
        self.assertIn("Expo", subject)
        self.assertIn("- ASL: مؤكد", body)
        self.assertIn("- Parking: يحتاج معلومات إضافية", body)

    def test_other_languages_get_english(self):
        subject, body = MAIN["build_status_email"]("en", "Expo", [("ASL", "NOT CONFIRMED")])
        self.assertTrue(subject.startswith("Update on your accessibility request"))
        self.assertIn("- ASL: Not confirmed", body)
        self.assertIn("Update", MAIN["build_status_email"](None, "Expo", [])[0])


class Notify(unittest.TestCase):
    def setUp(self):
        self.send = Mock()
        patcher = patch.dict(GLOBALS, send_test_mode_email=self.send)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_email_for_all_changes(self):
        with patch.object(db, "notify_status_changes", side_effect=fake_notify([("ASL", "CONFIRMED"), ("Parking", "UNAVAILABLE")])):
            self.assertTrue(MAIN["notify_user_of_status_changes"](1))
        self.send.assert_called_once()
        self.assertEqual(self.send.call_args.args[0], "user@secret.example")

    def test_no_changes_sends_nothing(self):
        with patch.object(db, "notify_status_changes", side_effect=fake_notify([])):
            self.assertFalse(MAIN["notify_user_of_status_changes"](1))
        self.send.assert_not_called()

    def test_failed_send_reports_false_and_hides_email(self):
        self.send.side_effect = smtplib.SMTPRecipientsRefused({"user@secret.example": (550, b"rejected")})
        updated = {"request_id": 1, "status": "CONFIRMED", "accommodations": {"ASL": "CONFIRMED"}}
        with patch.object(db, "notify_status_changes", side_effect=fake_notify([("ASL", "CONFIRMED")])), \
                patch.object(db, "update_request", return_value=updated), \
                patch.object(db, "default_user_id", return_value=1), \
                self.assertLogs(level="ERROR"):
            result = MAIN["update_request_status"](1, "confirmed", {"ASL": "confirmed"})
        self.assertEqual(result["status"], "updated")
        self.assertFalse(result["user_notified"])
        self.assertNotIn("secret.example", str(result))

    def test_notifier_is_not_an_agent_tool(self):
        self.assertNotIn("notify_user_of_status_changes", MAIN["agent"].tool_names)


if __name__ == "__main__":
    unittest.main()
