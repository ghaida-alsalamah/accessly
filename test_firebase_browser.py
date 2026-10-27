"""Browser regression for Firebase email-link flow; local demo emulators only."""
import os
import subprocess
import tempfile
import time
import unittest
from uuid import uuid4
from pathlib import Path
from urllib.parse import urlencode
import requests
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent


class FirebaseBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.getenv('ACCESSLY_IDENTITY_PROVIDER') != 'firebase'
            or not os.getenv('FIREBASE_PROJECT_ID', '').startswith('demo-')
            or any(not os.getenv(k, '').startswith(('127.0.0.1:', 'localhost:'))
                   for k in ['FIREBASE_AUTH_EMULATOR_HOST', 'FIRESTORE_EMULATOR_HOST'])):
            raise unittest.SkipTest('Local demo emulators required.')
        env = {**os.environ, 'PYTHON_DOTENV_DISABLED': '1', 'PORT': '8461',
               'ACCESSLY_DEV_BACKEND_URL': 'http://127.0.0.1:8013',
               'VITE_IDENTITY_PROVIDER': 'firebase', 'VITE_FIREBASE_PROJECT_ID': 'demo-accessly',
               'VITE_FIREBASE_API_KEY': 'fake-api-key',
               'VITE_FIREBASE_AUTH_EMULATOR_URL': 'http://127.0.0.1:9099',
               'VITE_FIREBASE_AUTH_CONTINUE_URL': 'http://127.0.0.1:8461/'}
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix='accessly-saved-event-test-')
        cls.addClassCleanup(cls.fixture_dir.cleanup)
        Path(cls.fixture_dir.name, 'accessly_saved_event_test_server.py').write_text("""
import os
assert os.getenv('FIREBASE_PROJECT_ID', '').startswith('demo-')
assert os.getenv('FIRESTORE_EMULATOR_HOST')
from copy import deepcopy
from types import SimpleNamespace
import api
from api import app
result = {'schema_version': 1, 'presentation_status': 'ready', 'message': 'Completed academic forum analysis.',
          'event': {'name': 'Saved Academic Forum', 'date': None, 'time': None, 'location': 'University hall',
                    'organizer': None, 'format': None, 'url': 'https://example.com/forum'},
          'accessibility_results': [], 'recommended_action': None, 'draft': None, 'requests': []}
class FakeAgent:
    model = SimpleNamespace()
    def __call__(self, message): return 'Existing completed forum analysis'
def load_user_profile(): return None
api.runpy.run_path = lambda path: {'agent': FakeAgent(), 'load_user_profile': load_user_profile}
api.format_result = lambda *args: deepcopy(result)
""")
        env['PYTHONPATH'] = cls.fixture_dir.name + os.pathsep + str(ROOT)
        cls.logs = open('/tmp/accessly-firebase-browser-servers.log', 'w')
        cls.processes = []
        cls.addClassCleanup(cls.stop_servers)
        cls.processes.append(subprocess.Popen([str(ROOT / '.venv/bin/python'), '-m', 'uvicorn', 'accessly_saved_event_test_server:app', '--host', '127.0.0.1', '--port', '8013'], cwd=ROOT, env=env, stdout=cls.logs, stderr=cls.logs))
        cls.processes.append(subprocess.Popen(['node', str(ROOT / 'frontend/node_modules/vite/bin/vite.js')], cwd=ROOT / 'frontend', env=env, stdout=cls.logs, stderr=cls.logs))
        for url in ['http://127.0.0.1:8013/health', 'http://127.0.0.1:8461/']:
            for _ in range(100):
                try:
                    if requests.get(url, timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.1)
            else:
                raise RuntimeError('Browser test server failed to start; see temporary server log.')

    @classmethod
    def stop_servers(cls):
        for process in cls.processes:
            process.terminate()
        for process in cls.processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=5)
        cls.logs.close()

    def codes(self):
        return requests.get('http://' + os.environ['FIREBASE_AUTH_EMULATOR_HOST'] + '/emulator/v1/projects/demo-accessly/oobCodes', timeout=15).json().get('oobCodes', [])

    def test_registration_login_edit_cancel_logout_and_returning_login(self):
        email = f'browser-{uuid4().hex}@example.com'
        from firebase_admin import auth
        from firebase_runtime import app
        import firestore_store as store
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                page.goto('http://127.0.0.1:8461/')
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                page.get_by_label('Full Name', exact=True).fill('Browser Test')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('Confirm Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('I agree to the Privacy Policy and Terms.').check()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Wheelchair access', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible(timeout=15000)
                self.assertFalse(any(c['email'] == email for c in self.codes()))
                user = auth.get_user_by_email(email, app=app())
                self.assertFalse(user.email_verified)
                self.assertEqual(store.get_user_profile(user.uid)['needs'], ['Wheelchair access'])
                page.get_by_role('button', name='Edit Accessibility').click()
                expect(page.get_by_role('button', name='Wheelchair access', exact=True)).to_have_attribute('aria-pressed', 'true')
                page.get_by_role('button', name='Accessible parking', exact=True).click()
                page.get_by_role('button', name='Cancel', exact=True).click()
                self.assertEqual(store.get_user_profile(user.uid)['needs'], ['Wheelchair access'])
                page.get_by_role('button', name='Edit Accessibility').click()
                page.get_by_role('button', name='Accessible parking', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible()
                self.assertEqual(len(store.get_user_profile(user.uid)['needs']), 2)
                page.get_by_role('button', name='Log Out').click()
                expect(page.get_by_role('button', name='Start Checking')).to_be_visible()
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Log In', exact=False).click()
                page.get_by_label('Email Address', exact=True).fill('invalid-email')
                expect(page.get_by_role('alert')).to_contain_text('valid email address')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('Wrong-Test-Password!')
                page.get_by_role('button', name='Login', exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('Incorrect email or password')
                page.get_by_role('button', name='Forgot password?', exact=True).click()
                expect(page.get_by_role('status')).to_contain_text('password reset instructions')
                self.assertTrue(any(c['email'] == email and c['requestType'] == 'PASSWORD_RESET' for c in self.codes()))
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_role('button', name='Login', exact=True).click()
                expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible()
                page.get_by_role('button', name='Edit Accessibility').click()
                self.assertEqual(page.locator('.setup-grid button[aria-pressed="true"]').count(), 2)
                self.assertEqual(page.get_by_text('Send Login Link', exact=True).count(), 0)
                self.assertFalse(errors)

            finally:
                browser.close()
                try:
                    user = auth.get_user_by_email(email, app=app())
                    auth.delete_user(user.uid, app=app())
                    store.client().recursive_delete(store._user(user.uid))
                except auth.UserNotFoundError:
                    pass

    def test_save_failure_retry_toast_navigation_and_reopen_without_analysis(self):
        email = f'saved-browser-{uuid4().hex}@example.com'
        from firebase_admin import auth
        from firebase_runtime import app
        import firestore_store as store
        import saved_events
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            actions = []
            page.on('request', lambda request: actions.append(request.url) if request.method == 'POST' and ('/api/events' in request.url or '/messages' in request.url) else None)
            try:
                page.goto('http://127.0.0.1:8461/')
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                page.get_by_label('Full Name', exact=True).fill('Saved Event Browser Test')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('Confirm Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('I agree to the Privacy Policy and Terms.').check()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Wheelchair access', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible()
                # Seed a completed conversation through the ordinary event API;
                # only model/research execution is replaced by the test fixture.
                page.evaluate("async () => { const {api, waitForJob}=await import('/src/api.ts'); const job=await waitForJob(await api('/events','POST',{url:'https://example.com/forum'}),()=>{}); sessionStorage.setItem('accessly:conversation:v2:https://example.com/forum',JSON.stringify({job,needs:['Wheelchair access'],turns:[{role:'agent',text:job.result.message,result:job.result,jobId:job.id}]})); }")
                # Enter the workspace using its existing Home/link flow.
                page.get_by_role('button', name='Drop a Link', exact=False).click()
                page.get_by_label('Event URL', exact=True).fill('https://example.com/forum')
                page.get_by_role('button', name='Process Event', exact=True).click()
                expect(page.get_by_role('button', name='Save Event', exact=True)).to_be_visible()
                self.assertEqual(len(actions), 1)
                def fail_save(route):
                    if route.request.method == 'POST':
                        route.fulfill(status=503, content_type='application/json', body='{"detail":"Simulated save failure. Please retry."}')
                    else: route.continue_()
                page.route('**/api/saved-events', fail_save)
                page.get_by_role('button', name='Save Event', exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('Simulated save failure')
                self.assertEqual(page.get_by_text('Event saved successfully.', exact=True).count(), 0)
                expect(page.get_by_role('button', name='Save Event', exact=True)).to_be_visible()
                page.unroute('**/api/saved-events', fail_save)
                page.get_by_role('button', name='Save Event', exact=True).click()
                expect(page.get_by_text('Event saved successfully.', exact=True)).to_be_visible()
                expect(page.get_by_role('button', name='Saved', exact=True)).to_be_disabled()
                expect(page.get_by_role('button', name='Open Saved Event', exact=True)).to_be_visible(timeout=10000)
                page.get_by_role('button', name='Open Saved Event', exact=True).click()
                expect(page.get_by_role('heading', name='Saved Academic Forum', exact=True)).to_be_visible()
                expect(page.get_by_text('Completed academic forum analysis.', exact=True)).to_be_visible()
                self.assertEqual(len(actions), 1)
                user = auth.get_user_by_email(email, app=app())
                self.assertEqual(len(saved_events.list_saved(user.uid)), 1)
            finally:
                browser.close()
                try:
                    user = auth.get_user_by_email(email, app=app())
                    auth.delete_user(user.uid, app=app())
                    store.client().recursive_delete(store._user(user.uid))
                except auth.UserNotFoundError:
                    pass

    def test_password_confirmation_short_password_and_existing_email(self):
        email = f'validation-{uuid4().hex}@example.com'
        from firebase_admin import auth
        from firebase_runtime import app
        user = auth.create_user(email=email, password='Test-Only-Accessly-Password-27!', app=app())
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto('http://127.0.0.1:8461/')
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                page.get_by_label('Full Name', exact=True).fill('Validation Test')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('short')
                expect(page.get_by_role('alert')).to_contain_text('at least 6 characters')
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('Confirm Password', exact=True).fill('Different-Password!')
                expect(page.get_by_role('alert')).to_contain_text('Passwords do not match')
                page.get_by_label('I agree to the Privacy Policy and Terms.').check()
                expect(page.get_by_role('button', name='Continue', exact=False)).to_be_disabled()
                page.get_by_label('Confirm Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Wheelchair access', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('alert')).to_contain_text('already exists')
            finally:
                browser.close()
                auth.delete_user(user.uid, app=app())

    def test_registration_uses_saved_profile_without_an_extra_read(self):
        email = f'completion-{uuid4().hex}@example.com'
        from firebase_admin import auth
        from firebase_runtime import app
        import firestore_store as store
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            reads = []
            def hold_extra_read(route):
                if route.request.method == 'GET': reads.append(route)
                else: route.continue_()
            page.route('**/api/profile', hold_extra_read)
            try:
                page.goto('http://127.0.0.1:8461/')
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                page.get_by_label('Full Name', exact=True).fill('Registration Completion Test')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('Confirm Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('I agree to the Privacy Policy and Terms.').check()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Wheelchair access', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                try:
                    expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible(timeout=8000)
                except AssertionError:
                    user = auth.get_user_by_email(email, app=app())
                    profile = store.get_user_profile(user.uid)
                    self.fail('Auth user created; profile/needs saved=' + str(profile is not None and profile['needs'] == ['Wheelchair access']) + '; extra profile GET pending=' + str(bool(reads)) + '; Creating account still displayed=' + str(page.get_by_role('button', name='Creating account…', exact=False).count() > 0))
                self.assertEqual(len(reads), 0)
                signed_in = page.evaluate("async () => !!(await import('/src/firebase.ts')).firebaseAuth().currentUser")
                self.assertTrue(signed_in)
            finally:
                browser.close()
                try:
                    user = auth.get_user_by_email(email, app=app())
                    auth.delete_user(user.uid, app=app()); store.client().recursive_delete(store._user(user.uid))
                except auth.UserNotFoundError: pass

    def test_registration_save_failure_preserves_session_and_retries_same_user(self):
        email = f'retry-{uuid4().hex}@example.com'
        from firebase_admin import auth
        from firebase_runtime import app
        import firestore_store as store
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            signups = []
            page.on('request', lambda request: signups.append(request.url) if 'accounts:signUp' in request.url else None)
            def fail_save(route):
                route.fulfill(status=401, content_type='application/json', body='{"detail":"Temporary profile save failure"}')
            page.route('**/api/profile/complete', fail_save)
            try:
                page.goto('http://127.0.0.1:8461/')
                page.get_by_role('button', name='Start Checking').click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                page.get_by_label('Full Name', exact=True).fill('Registration Retry Test')
                page.get_by_label('Email Address', exact=True).fill(email)
                page.get_by_label('Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('Confirm Password', exact=True).fill('Test-Only-Accessly-Password-27!')
                page.get_by_label('I agree to the Privacy Policy and Terms.').check()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Wheelchair access', exact=True).click()
                page.get_by_role('button', name='Continue', exact=False).click()
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('alert')).to_contain_text('Temporary profile save failure')
                expect(page.get_by_role('button', name='Create Account', exact=False)).to_be_enabled()
                uid = page.evaluate("async () => (await import('/src/firebase.ts')).firebaseAuth().currentUser?.uid")
                self.assertTrue(uid)
                page.unroute('**/api/profile/complete', fail_save)
                def hold_save(route):
                    pass
                page.route('**/api/profile/complete', hold_save)
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('alert')).to_contain_text('timed out', timeout=35000)
                expect(page.get_by_role('button', name='Create Account', exact=False)).to_be_enabled()
                self.assertEqual(page.evaluate("async () => (await import('/src/firebase.ts')).firebaseAuth().currentUser?.uid"), uid)
                page.unroute('**/api/profile/complete', hold_save)
                page.get_by_role('button', name='Create Account', exact=False).click()
                expect(page.get_by_role('button', name='Edit Accessibility')).to_be_visible()
                self.assertEqual(page.evaluate("async () => (await import('/src/firebase.ts')).firebaseAuth().currentUser?.uid"), uid)
                self.assertEqual(len(signups), 1)
                self.assertEqual(store.get_user_profile(uid)['needs'], ['Wheelchair access'])
            finally:
                browser.close()
                try:
                    user = auth.get_user_by_email(email, app=app())
                    auth.delete_user(user.uid, app=app())
                    store.client().recursive_delete(store._user(user.uid))
                except auth.UserNotFoundError:
                    pass
