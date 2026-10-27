"""Firebase integration tests run ONLY against local emulators and demo projects."""
import os
import unittest
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from uuid import uuid4


def setUpModule():
    required = ('FIREBASE_AUTH_EMULATOR_HOST', 'FIRESTORE_EMULATOR_HOST')
    if (os.getenv('ACCESSLY_IDENTITY_PROVIDER') != 'firebase'
        or not os.getenv('FIREBASE_PROJECT_ID', '').startswith('demo-')
        or any(not os.getenv(k, '').startswith(('127.0.0.1:', 'localhost:')) for k in required)):
        raise unittest.SkipTest('Requires local Auth/Firestore emulators and a demo- project.')


class FirebaseIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import api
        import firestore_store
        from fastapi.testclient import TestClient
        cls.api = api
        cls.store = firestore_store
        cls.client = TestClient(api.app)

    def setUp(self):
        self.email = f'accessly-{uuid4().hex}@example.com'
        self.name = 'Firebase Test'
        self.ids = []
        self.password_headers = {}
        self.mail_guard = patch('smtplib.SMTP', side_effect=AssertionError('SMTP forbidden'))
        self.pg_guard = patch('psycopg.connect', side_effect=AssertionError('PostgreSQL forbidden'))
        self.mail_guard.start(); self.pg_guard.start()
        self.addCleanup(self.mail_guard.stop); self.addCleanup(self.pg_guard.stop)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        from firebase_admin import auth
        from firebase_runtime import app
        for uid in self.ids:
            try: auth.delete_user(uid, app=app())
            except auth.UserNotFoundError: pass
            self.store.client().recursive_delete(self.store._user(uid))

    PASSWORD = 'Test-Only-Accessly-Password-27!'

    def auth_request(self, method, body):
        import requests
        return requests.post('http://' + os.environ['FIREBASE_AUTH_EMULATOR_HOST'] +
            '/identitytoolkit.googleapis.com/v1/accounts:' + method + '?key=fake-key', json=body, timeout=15)

    def register(self, email=None, needs=None):
        email = email or self.email
        response = self.auth_request('signUp', {'email': email, 'password': self.PASSWORD, 'returnSecureToken': True})
        self.assertEqual(response.status_code, 200)
        uid = response.json()['localId']; self.ids.append(uid)
        headers = {'Authorization': 'Bearer ' + response.json()['idToken']}
        self.password_headers[uid] = headers
        saved = self.client.post('/api/profile/complete', headers=headers, json={
            'name': self.name, 'preferred_language': 'en', 'consent': True,
            'needs': needs or ['Wheelchair access', 'Other: Quiet seating']})
        self.assertEqual(saved.status_code, 200, saved.text)
        return uid

    def login(self, email, password=None):
        response = self.auth_request('signInWithPassword', {'email': email, 'password': password or self.PASSWORD, 'returnSecureToken': True})
        self.assertEqual(response.status_code, 200)
        return {'Authorization': 'Bearer ' + response.json()['idToken']}

    def test_registration_saves_profile_and_signs_in_without_email(self):
        import requests
        from firebase_admin import auth
        from firebase_runtime import app
        uid = self.register()
        self.assertFalse(auth.get_user(uid, app=app()).email_verified)
        self.assertEqual(self.store.get_user_profile(uid)['needs'], ['Wheelchair access', 'Other: Quiet seating'])
        response = self.client.get('/api/profile')
        self.assertEqual(response.status_code, 401)
        signup_headers = self.password_headers[uid]
        self.assertEqual(self.client.get('/api/profile', headers=signup_headers).status_code, 200)
        self.assertFalse(auth.get_user(uid, app=app()).email_verified)
        root = 'http://' + os.environ['FIREBASE_AUTH_EMULATOR_HOST']
        codes = requests.get(root + '/emulator/v1/projects/' + os.environ['FIREBASE_PROJECT_ID'] + '/oobCodes', timeout=15).json()
        self.assertFalse(any(c['email'] == self.email for c in codes.get('oobCodes', [])))
        duplicate = self.client.post('/api/auth/register', json={'name': 'Overwrite', 'email': self.email,
             'preferred_language': 'ar', 'consent': True, 'needs': ['Changed']})
        self.assertEqual(duplicate.status_code, 410)
        duplicate_auth = self.auth_request('signUp', {'email': self.email, 'password': self.PASSWORD, 'returnSecureToken': True})
        self.assertEqual(duplicate_auth.status_code, 400)
        self.assertIn('EMAIL_EXISTS', duplicate_auth.json()['error']['message'])
        self.assertEqual(self.store.get_user_profile(uid)['name'], self.name)

    def test_login_edit_reload_and_isolation(self):
        uid = self.register()
        headers = self.login(self.email)
        profile = self.client.get('/api/profile', headers=headers)
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertNotIn('email', profile.json())
        edited = self.client.post('/api/profile', headers=headers, json={'needs': ['Other: Quiet seating', 'Hearing support']})
        self.assertEqual(edited.status_code, 200, edited.text)
        self.assertEqual(self.client.get('/api/profile', headers=headers).json()['needs'], ['Other: Quiet seating', 'Hearing support'])
        inactive = self.store._user(uid).collection('needs').document(self.store._need_id('Wheelchair access')).get().to_dict()
        self.assertFalse(inactive['is_active'])
        self.assertEqual(self.client.get('/api/profile').status_code, 401)
        other_email = f'accessly-{uuid4().hex}@example.com'
        other = self.register(other_email, ['Different need'])
        other_headers = self.login(other_email)
        self.assertEqual(self.client.get('/api/profile', headers=other_headers).json()['needs'], ['Different need'])
        self.assertNotEqual(uid, other)

    def test_requests_snapshot_status_and_cross_user_access(self):
        uid = self.register()
        headers = self.login(self.email)
        record = self.store.create_request(uid, 'Academic event', 'https://example.invalid/event', 'organizer@example.com', 'Subject')
        self.assertRegex(record['request_id'], r'^REQ-\d+$')
        self.assertEqual(record['status'], 'PENDING')
        request_id = record['request_id']
        self.store.save_user_needs(uid, ['New need'])
        updated = self.store.update_request(uid, request_id, {'Wheelchair access': 'CONFIRMED'}, 'PARTIALLY CONFIRMED')
        self.assertEqual(updated['accommodations']['Wheelchair access'], 'CONFIRMED')
        self.assertNotIn('New need', updated['accommodations'])
        rows = self.client.get('/api/requests', headers=headers).json()
        self.assertEqual(rows, [updated])
        child = self.store._request_ref(uid, request_id).collection('request_needs').document(self.store._need_id('Wheelchair access')).get().to_dict()
        self.assertEqual(child['status'], 'CONFIRMED')
        other_email = f'accessly-{uuid4().hex}@example.com'
        other = self.register(other_email)
        self.assertIsNone(self.store.get_request(other, request_id))
        self.assertIsNone(self.store.update_request(other, request_id, {}, 'CONFIRMED'))
        self.assertEqual(self.client.get('/api/requests', headers=self.login(other_email)).json(), [])
        with self.assertRaises(ValueError):
            self.store.update_request(uid, request_id, {'Wheelchair access': 'INVALID'})

    def test_auth_rejects_forgery_and_cross_user_jobs(self):
        self.register(); headers = self.login(self.email)
        self.api.sessions['firebase-test-session'] = None
        self.api.session_context['firebase-test-session'] = {'owner': 'another-user'}
        self.api.jobs['firebase-test-job'] = {'session_id': 'firebase-test-session', 'status': 'processing'}
        try:
            self.assertEqual(self.client.get('/api/jobs/firebase-test-job', headers=headers).status_code, 404)
            self.assertEqual(self.client.get('/api/profile', headers={'Authorization': 'Bearer forged'}).status_code, 401)
            self.assertEqual(self.client.post('/api/auth/send-otp', json={'email': self.email}).status_code, 404)
        finally:
            self.api.sessions.pop('firebase-test-session', None)
            self.api.session_context.pop('firebase-test-session', None)
            self.api.jobs.pop('firebase-test-job', None)

    def test_missing_profile_recovery_requires_authenticated_consent(self):
        from firebase_admin import auth
        from firebase_runtime import app
        user = auth.create_user(email=self.email, password=self.PASSWORD, app=app()); self.ids.append(user.uid)
        headers = self.login(self.email)
        self.assertEqual(self.client.get('/api/profile', headers=headers).status_code, 404)
        body = {'name': self.name, 'preferred_language': 'en', 'consent': True}
        self.assertEqual(self.client.post('/api/profile/complete', json=body).status_code, 401)
        self.assertEqual(self.client.post('/api/profile/complete', json={**body, 'consent': False}, headers=headers).status_code, 422)
        self.assertEqual(self.client.post('/api/profile/complete', json=body, headers=headers).status_code, 200)
        self.assertEqual(self.client.post('/api/profile', json={'needs': ['Wheelchair access']}, headers=headers).status_code, 200)

    def test_revoked_disabled_and_deleted_accounts(self):
        from firebase_admin import auth
        from firebase_runtime import app
        uid = self.register(); headers = self.login(self.email)
        import time
        time.sleep(1.1)
        auth.revoke_refresh_tokens(uid, app=app())
        self.assertEqual(self.client.get("/api/profile", headers=headers).status_code, 401)
        headers = self.login(self.email)
        self.store.create_request(uid, "Academic event", "https://example.com/event", "organizer@example.com", "Subject")
        auth.update_user(uid, disabled=True, app=app())
        self.assertEqual(self.client.get('/api/profile', headers=headers).status_code, 401)
        auth.update_user(uid, disabled=False, app=app())
        self.assertEqual(self.client.delete('/api/account', headers=headers).status_code, 204)
        self.assertFalse(self.store._user(uid).get().exists)
        self.assertEqual(list(self.store._user(uid).collection('needs').stream()), [])
        self.assertEqual(list(self.store._user(uid).collection('requests').stream()), [])
        self.assertEqual(self.client.get('/api/profile', headers=headers).status_code, 401)

    def test_event_job_polling_preserves_uid_and_response_contract(self):
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from deployment_runtime import current_user_id
        uid = self.register(); headers = self.login(self.email)
        globals_ = {}
        exec('def load_user_profile(): return None', globals_)
        def run_agent(message):
            self.assertEqual(current_user_id(), uid)
            self.assertEqual(globals_['USER_ID'], uid)
            self.assertEqual(self.store.get_user_profile(uid)['name'], self.name)
            return 'Mock academic event research'
        agent = Mock(side_effect=run_agent)
        agent.model = SimpleNamespace()
        namespace = {'agent': agent, 'load_user_profile': globals_['load_user_profile']}
        with patch.object(self.api.runpy, 'run_path', return_value=namespace), patch.object(self.api, 'format_result', return_value={'summary': 'Test result'}):
            response = self.client.post('/api/events', json={'url': 'https://example.com/event'}, headers=headers)
            self.assertEqual(response.status_code, 202, response.text)
            job = response.json()
            try:
                for _ in range(100):
                    response = self.client.get('/api/jobs/' + job['id'], headers=headers)
                    self.assertEqual(response.status_code, 200)
                    if response.json()['status'] != 'processing': break
                    time.sleep(.02)
                result = response.json()
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(result['session_id'], job['session_id'])
                self.assertEqual(result['result']['requests'], [])
                self.assertEqual(result['response'], 'Mock academic event research')
            finally:
                self.api.jobs.pop(job['id'], None)
                self.api.sessions.pop(job['session_id'], None)
                self.api.session_context.pop(job['session_id'], None)

    def test_browser_firestore_access_is_denied_by_rules(self):
        import requests
        uid = self.register(); headers = self.login(self.email)
        url = ('http://' + os.environ['FIRESTORE_EMULATOR_HOST'] +
               '/v1/projects/demo-accessly/databases/(default)/documents/users/' + uid)
        response = requests.get(url, headers=headers, timeout=15)
        self.assertEqual(response.status_code, 403)

    def test_password_reset_for_existing_passwordless_uid_preserves_profile(self):
        import requests
        from firebase_admin import auth
        from firebase_runtime import app
        user = auth.create_user(email=self.email, app=app()); self.ids.append(user.uid)
        self.store.complete_profile(user.uid, self.name, 'en', ['Wheelchair access'])
        response = self.auth_request('sendOobCode', {'requestType': 'PASSWORD_RESET', 'email': self.email})
        self.assertEqual(response.status_code, 200)
        codes = requests.get('http://' + os.environ['FIREBASE_AUTH_EMULATOR_HOST'] + '/emulator/v1/projects/' + os.environ['FIREBASE_PROJECT_ID'] + '/oobCodes', timeout=15).json()['oobCodes']
        code = next(c['oobCode'] for c in reversed(codes) if c['email'] == self.email)
        reset = self.auth_request('resetPassword', {'oobCode': code, 'newPassword': self.PASSWORD})
        self.assertEqual(reset.status_code, 200)
        headers = self.login(self.email)
        self.assertEqual(auth.get_user_by_email(self.email, app=app()).uid, user.uid)
        self.assertEqual(self.client.get('/api/profile', headers=headers).json()['needs'], ['Wheelchair access'])
        raw = self.store._user(user.uid).get().to_dict()
        self.assertFalse(any('password' in key.lower() for key in raw))
        self.assertEqual(self.client.post('/api/auth/register', json={'name': 'Overwrite', 'email': self.email, 'preferred_language': 'en', 'consent': True}).status_code, 410)

    def test_invalid_credentials_and_profile_retry_preserve_data(self):
        uid = self.register()
        invalid = self.auth_request('signInWithPassword', {'email': self.email, 'password': 'Wrong-Test-Password!', 'returnSecureToken': True})
        self.assertEqual(invalid.status_code, 400)
        original = self.store._user(uid).get().to_dict()
        response = self.client.post('/api/profile/complete', headers=self.password_headers[uid], json={'name': 'Different', 'preferred_language': 'ar', 'consent': True, 'needs': ['Overwrite']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.store._user(uid).get().to_dict(), original)
        self.assertEqual(self.store.get_user_profile(uid)['needs'], ['Wheelchair access', 'Other: Quiet seating'])
        self.assertNotIn('password', original)

    def saved_job(self, uid):
        from uuid import uuid4
        job_id = str(uuid4()); session_id = str(uuid4())
        result = {'schema_version': 1, 'presentation_status': 'ready', 'message': 'Completed academic event analysis',
                  'event': {'name': 'Saved Academic Forum', 'url': 'https://example.com/forum'},
                  'accessibility_results': [], 'recommended_action': None, 'draft': None, 'requests': []}
        self.api.session_context[session_id] = {'owner': uid, 'url': 'https://example.com/forum', 'needs': ['Wheelchair access']}
        self.api.sessions[session_id] = None
        self.api.jobs[job_id] = {'id': job_id, 'session_id': session_id, 'status': 'completed', 'response': 'Original agent output', 'result': result}
        def cleanup():
            self.api.jobs.pop(job_id, None); self.api.sessions.pop(session_id, None); self.api.session_context.pop(session_id, None)
        self.addCleanup(cleanup)
        return job_id, session_id, result

    def test_save_event_idempotent_reopen_and_user_isolation_without_agent(self):
        uid = self.register(); headers = self.password_headers[uid]
        job_id, session_id, result = self.saved_job(uid)
        body = {'job_id': job_id, 'conversation': [{'role': 'agent', 'text': result['message']}]}
        with patch.object(self.api, 'submit', side_effect=AssertionError('Agent must not run')):
            first = self.client.post('/api/saved-events', json=body, headers=headers)
            self.assertEqual(first.status_code, 200, first.text)
            again = self.client.post('/api/saved-events', json=body, headers=headers)
            self.assertEqual(again.json()['id'], first.json()['id'])
            rows = self.client.get('/api/saved-events', headers=headers).json()
            self.assertEqual(len(rows), 1)
            event_id = rows[0]['id']
            # Saved data survives expiration of the in-memory analysis session.
            self.api.jobs.pop(job_id); self.api.session_context.pop(session_id)
            opened = self.client.get('/api/saved-events/' + event_id, headers=headers)
            self.assertEqual(opened.status_code, 200)
            self.assertEqual(opened.json()['result'], result)
            self.assertEqual(opened.json()['response'], 'Original agent output')
            self.assertEqual(opened.json()['event_url'], 'https://example.com/forum')
            self.assertEqual(opened.json()['status'], 'completed')
            other = self.register('other-' + self.email)
            other_headers = self.password_headers[other]
            self.assertEqual(self.client.get('/api/saved-events', headers=other_headers).json(), [])
            self.assertEqual(self.client.get('/api/saved-events/' + event_id, headers=other_headers).status_code, 404)
            self.assertEqual(self.client.get('/api/saved-events/' + event_id).status_code, 401)

    def test_save_rejects_processing_unavailable_foreign_and_failed_write(self):
        uid = self.register(); headers = self.password_headers[uid]
        job_id, session_id, result = self.saved_job(uid)
        body = {'job_id': job_id}
        self.api.jobs[job_id]['status'] = 'processing'
        self.assertEqual(self.client.post('/api/saved-events', json=body, headers=headers).status_code, 409)
        self.api.jobs[job_id]['status'] = 'completed'
        result['presentation_status'] = 'unavailable'
        self.assertEqual(self.client.post('/api/saved-events', json=body, headers=headers).status_code, 409)
        result['presentation_status'] = 'ready'
        other = self.register('other-' + self.email)
        other_headers = self.password_headers[other]
        self.assertEqual(self.client.post('/api/saved-events', json=body, headers=other_headers).status_code, 404)
        with patch('saved_events.save_snapshot', side_effect=RuntimeError('Simulated write failure')):
            self.assertEqual(self.client.post('/api/saved-events', json=body, headers=headers).status_code, 503)
        self.assertEqual(self.client.get('/api/saved-events', headers=headers).json(), [])
