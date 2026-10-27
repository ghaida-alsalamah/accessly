"""Isolated approved-email transport tests: no agent, database, or real mail."""
import ast
from pathlib import Path
import os
import smtplib
import ssl
import unicodedata
import unittest
from email.message import EmailMessage
from unittest.mock import Mock, patch
import certifi


def load_send():
    tree = ast.parse(Path(__file__).with_name('main.py').read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('clean_text', 'send_accommodation_email')]
    for node in functions:
        node.decorator_list = []
    namespace = dict(os=os, smtplib=smtplib, ssl=ssl, certifi=certifi,
                     unicodedata=unicodedata, EmailMessage=EmailMessage)
    exec(compile(ast.Module(body=functions, type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace['send_accommodation_email']


class AccommodationEmail(unittest.TestCase):
    def setUp(self):
        self.send = load_send()
        env = patch.dict(os.environ, {
            'ACCESSLY_EMAIL': 'sender@example.com',
            'ACCESSLY_EMAIL_APP_PASSWORD': 'test-password',
            'ACCESSLY_TEST_RECIPIENT': 'test@example.com',
        })
        env.start(); self.addCleanup(env.stop)
        smtp_patch = patch('smtplib.SMTP')
        self.factory = smtp_patch.start(); self.addCleanup(smtp_patch.stop)
        self.smtp = self.factory.return_value
        self.smtp.send_message.return_value = {}
        self.args = ('organizer@example.com', 'Approved subject', 'Approved body')

    def test_success_requires_smtp_acceptance_and_verified_certifi_tls(self):
        real_context = ssl.create_default_context
        with patch('ssl.create_default_context', wraps=real_context) as context:
            result = self.send(*self.args)
        self.assertEqual(result['status'], 'sent')
        self.factory.assert_called_once_with('smtp.gmail.com', 587, timeout=30)
        context.assert_called_once_with(cafile=certifi.where())
        tls = self.smtp.starttls.call_args.kwargs['context']
        self.assertTrue(tls.check_hostname)
        self.assertEqual(tls.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(self.smtp.ehlo.call_count, 2)
        self.smtp.login.assert_called_once_with('sender@example.com', 'test-password')
        self.smtp.send_message.assert_called_once()
        self.smtp.close.assert_called_once()
        self.assertEqual(self.smtp.send_message.call_args.args[0]['To'], 'test@example.com')

    def test_authentication_failure_preserves_draft_and_never_sends(self):
        self.smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b'Bad credentials')
        result = self.send(*self.args)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('App Password', result['message'])
        self.assertEqual(result['draft'], dict(zip(('to', 'subject', 'body'), self.args)))
        self.smtp.send_message.assert_not_called()

    def test_disconnect_is_not_reported_as_a_certificate_error(self):
        self.smtp.login.side_effect = smtplib.SMTPServerDisconnected('closed')
        result = self.send(*self.args)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('authentication', result['message'])
        self.assertNotIn('certificate', result['message'])
        self.smtp.send_message.assert_not_called()

    def test_recipient_refusal_is_not_success(self):
        self.smtp.send_message.return_value = {'test@example.com': (550, b'refused')}
        self.assertEqual(self.send(*self.args)['status'], 'failed')

    def test_data_rejection_is_not_success(self):
        self.smtp.send_message.side_effect = smtplib.SMTPDataError(554, b'rejected')
        self.assertEqual(self.send(*self.args)['status'], 'failed')

    def test_tls_failure_cannot_send(self):
        self.smtp.starttls.side_effect = ssl.SSLCertVerificationError('untrusted')
        result = self.send(*self.args)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('certificate', result['message'])
        self.smtp.login.assert_not_called()
        self.smtp.send_message.assert_not_called()


if __name__ == '__main__':
    unittest.main()
