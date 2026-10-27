# Firebase integration — opt-in, no production cutover

PostgreSQL remains the default. No Neon migration, export, or deletion is automatic.
Restore point before this work: `restore/pre-firebase-20261026-105043`.

## Configuration

Backend: set `ACCESSLY_IDENTITY_PROVIDER=firebase`, `FIREBASE_PROJECT_ID=accey-80215`,
and `GOOGLE_APPLICATION_CREDENTIALS` to the local or mounted service-account JSON.
Keep the key out of Git and Docker; do not paste it into browser configuration.
Frontend: set `VITE_IDENTITY_PROVIDER=firebase` and
`VITE_FIREBASE_AUTH_CONTINUE_URL` in **frontend/.env.local** or the Vite build
process environment. The repository root .env is not Vite's frontend env file.
Use `http://localhost:8443/` for local testing only; use HTTPS in production.
Restart both processes after changing providers. Both must use the same provider.
Docker frontend builds accept `--build-arg VITE_IDENTITY_PROVIDER=firebase` and
`--build-arg VITE_FIREBASE_AUTH_CONTINUE_URL=https://your-domain/`. Keep the backend
provider aligned; the default Docker build still uses PostgreSQL.

The supplied web app configuration is in `frontend/src/firebase.ts` and contains
public browser configuration, not Admin credentials.

Enable Firebase Email/Password + Email Link, authorize the exact hostname
(including localhost for development), and publish `firestore.rules` after review.
No Firebase Hosting deployment is required to run the existing Vite/FastAPI app.

## Behavior

Create Account creates an **unverified** Firebase Auth user and a Firestore
profile/needs batch. Only after that batch commits, the backend issues a Firebase
custom token for the just-created UID. The frontend exchanges it through Firebase
Auth, loads the saved profile, and goes directly to Home. Registration sends no
email, creates no password, and does not navigate to Login. The short-lived custom
token is kept only in memory for retries and returned with Cache-Control: no-store.
Duplicate registration never issues a token for an existing account.

The initial session does not establish ownership of the supplied email. It is
accepted only with the server-issued registration claim and custom sign-in
provider, while the Firebase user remains unverified. Once email-link verification
establishes ownership, the backend rejects old registration sessions and custom
token replays. Ordinary login sessions still require a verified email.

Login alone requests a Firebase email link. Opening that link returns to the
existing Login screen; Continue completes login and loads the existing Firestore
profile/needs. On another browser/device, enter the same email to complete login.
Registration data is already saved against the UID and is not placed into a URL.

Firebase can also create an Auth identity when an unregistered email follows a
login link. A missing Accessly profile routes to existing onboarding; a protected
completion endpoint requires name/consent before saving the profile/preferences.
A partial registration failure is recoverable the same way. An unauthenticated
repeat registration never overwrites an existing user's data.

The SDK persists/refreshes Firebase login. API requests obtain current ID tokens;
backend verification checks the registration-session policy, email verification for
ordinary login, revocation and disabled accounts.
Logout signs out of Firebase and clears existing conversation caches, returning to
the existing Intro. Email link query parameters are removed after completion.
Profiles exclude email from the agent context.

## Storage and contracts

`users/{uid}` stores registration/language/consent. Its `needs` subcollection uses
stable hashes of need names, explicit ordering, and inactive rather than deleted
preferences. `requests/{REQ-number}` stores the existing public request shape and
an accommodations snapshot. `request_needs` stores individual statuses linked by
stable need IDs. Transactions keep snapshots/statuses consistent and allocate
unique public request IDs through `_accessly_counters/requests`.
Firestore IDs are owner-scoped and every backend operation derives its owner from
a verified token. Admin SDK bypasses Firestore rules; never rely on rules alone.
Browser reads/writes are denied by `firestore.rules`.
Account deletion removes Auth first and recursively deletes Firestore descendants;
Auth and Firestore are separate services, so interrupted cleanup needs retry.

Existing PostgreSQL users are NOT automatically mapped by email or migrated.
Their data needs a separately reviewed identity mapping/export/import. The current
Firebase request counter is for fresh data; a future import must seed it above
all imported request IDs before writes. Never switch providers silently.

## Verification

Install backend requirements and frontend dependencies normally. Run:

```sh
PYTHON_DOTENV_DISABLED=1 ACCESSLY_IDENTITY_PROVIDER=postgres ACCESSLY_PUBLIC_MODE=0 .venv/bin/python -m unittest test_auth
cd frontend
npx tsc --noEmit
npm run build
```

Firebase tests require local emulators and a **demo-** project, never production:

```sh
firebase emulators:exec --project demo-accessly --only auth,firestore \
  'PYTHON_DOTENV_DISABLED=1 ACCESSLY_IDENTITY_PROVIDER=firebase ACCESSLY_PUBLIC_MODE=0 FIREBASE_PROJECT_ID=demo-accessly .venv/bin/python -m unittest test_firebase test_firebase_browser'
```

For browser tests build/run with `VITE_IDENTITY_PROVIDER=firebase` and
`VITE_FIREBASE_AUTH_EMULATOR_URL=http://127.0.0.1:9099`.
Do not set emulator variables in production. Emulator email links are local only.

## Before any cutover

Verify real email delivery with your own test account, authorized return URL,
profile edits/reload/logout and one complete approved event run. Review deployed
rules/IAM, quotas and registration abuse controls (Admin account creation is not
Firebase client-rate-limited). Review data transfer separately. PostgreSQL rollback
is a configuration change only before new Firebase writes; later writes need
reconciliation. Keep all PostgreSQL/custom-auth files and configuration until
explicit removal approval. Keep Gmail credentials for agent accommodation mail
and organizer reply checks even after Firebase login replaces OTP mail.

## Implementation verification and remaining setup

Completed against isolated `demo-accessly` Auth/Firestore emulators:
10 integration/browser tests passed, including direct authenticated registration without email,
email-link login in same and different browser contexts, stored preferences,
editing Continue/Cancel, logout to Intro, returning login, request snapshots and
statuses, cross-user job/request isolation, mocked event-job creation/polling,
revoked/disabled/deleted accounts, and denied direct browser Firestore access.
The existing 31 PostgreSQL/auth tests passed; TypeScript, Firebase/default builds,
Python syntax and pip dependency consistency passed. Live Firebase email delivery,
Admin IAM access and live agent execution have NOT been verified by these tests.
The browser test requires Playwright Chromium installed in the configured path.
Firebase core overrides prevent duplicate App instances and preserve Node 22
compatibility; the gRPC override avoids advisories in the added dependency tree.
Existing Vite/source-map-js audit findings were left outside this migration scope.

At inspection time, neither FIREBASE_PROJECT_ID nor GOOGLE_APPLICATION_CREDENTIALS
was present in the **saved on-disk root .env**. Save those settings locally before
any separate live Firebase test. No .env values or service-account contents were
printed. The private key is now ignored by Git and Docker. No hosted Firebase
writes, Neon access, migrations, production switch, or PostgreSQL removal occurred.
Firestore rules have only been applied to emulators, not deployed to the project.

Files added: `.dockerignore`, `firebase_runtime.py`, `firestore_store.py`,
`persistence.py`, `frontend/src/firebase.ts`, `firebase.json`, `firestore.rules`,
`test_firebase.py`, `test_firebase_browser.py`, and this document.
Files edited: `.gitignore`, `.env.production.example`, `api.py`,
`deployment_runtime.py`, `main.py` (persistence import only), both Dockerfiles,
`requirements-production.txt`, `frontend/package.json`, both frontend lockfiles,
`frontend/src/api.ts`, and the authentication/onboarding parts of
`frontend/src/App.tsx`.
Protected UI/assets, styles, workspace/result modules, research/prompt logic,
and PostgreSQL modules were verified unchanged from before this implementation.

Registration/login separation update: only api.py, firebase_runtime.py,
frontend/src/firebase.ts, frontend/src/App.tsx, the two Firebase test files,
and this document changed. Registration now uses Firebase custom-token sign-in;
PostgreSQL OTP behavior and all event/agent/research/result code remain unchanged.

## Save Event / Previous Events

The Firebase workspace adds Save Event below the completed conversation/composer.
It is available only for a completed job whose presentation is ready. It posts the
owned job ID and display-only conversation text to POST /api/saved-events; this
endpoint copies the authoritative existing job result, raw response, event URL,
needs and completed status. It never invokes submit, the model, research, or polling.
Snapshots live at users/{uid}/saved_events/{sha256(job_id)}. A transactional create
makes retries/double clicks idempotent for the same completed analysis. Separate
completed analysis jobs may be saved independently. The write is Firestore-only;
PostgreSQL mode does not expose the save control or provide an alternate save store.

While saving, controls are disabled to avoid submitting another agent action before
navigation. On confirmed success a small green 'Event saved successfully.' toast
appears for 1.8 seconds, then the app navigates to its existing Previous Events/My
Requests view. A saved-events section is added above the unchanged request list.
GET /api/saved-events lists the most recent 100 snapshots. Opening one calls
GET /api/saved-events/{id} and uses the unchanged AgentResult renderer without
reply/send callbacks. Existing jobs/sessions are not required for reopening.
Save/read/list endpoints use the authenticated UID and never accept a client UID.
The Firestore browser-deny rules remain unchanged; FastAPI uses the Admin SDK.
A result larger than the supported snapshot budget is rejected with a clear error
rather than truncated or navigated away from. Any write failure leaves the live
result displayed, permits retry, and shows no success toast.

Save-flow verification: 13 Firebase emulator/browser tests passed, plus 31 existing
PostgreSQL/auth tests, TypeScript and Firebase build. Tests cover ownership,
incomplete/unavailable results, failed saves/retry, duplicate saves, persistence
beyond expired jobs, toast/navigation, and reopening without another analysis.
No live model/research call or email was used by these tests.

Files added for Save Event: saved_events.py, frontend/src/SaveEventAction.tsx,
frontend/src/SavedEvents.tsx. Files edited: api.py (additive route installation),
frontend/src/AgentWorkspace.tsx (footer/control lock and saved-events slot only),
frontend/src/App.tsx (Previous Events view import), both Dockerfiles (copy the new
backend module), both Firebase test files, and this document. AgentResult.tsx,
presentation.ts, index.css, Intro assets, prompts, research and polling are unchanged.

## Current authentication: Firebase Email/Password

This section supersedes the earlier Email Link/custom-token registration notes.
The active Firebase UI uses createUserWithEmailAndPassword for new registration,
signInWithEmailAndPassword for Login, and sendPasswordResetEmail for recovery.
Email-link send/completion functions are removed from the frontend. The Firebase
public registration endpoint no longer mints custom tokens (410); PostgreSQL's
existing OTP fallback is unchanged. Existing legacy sessions/data are not deleted.

The first registration step adds Password/Confirm Password in existing field
styles, validates minimum 6 characters and matching confirmation, and retains
Back/Continue behavior. Passwords exist only in React memory and Firebase SDK
calls, are cleared after successful signup/logout, and never go to Accessly API,
Firestore or browser storage. Firebase enforces any additional project password
policy. After Auth creates/signs in the UID, /api/profile/complete atomically
creates the existing profile and needs documents. Retry does not overwrite an
existing profile/preferences. Email is read from the Firebase Auth user on the
server. Ordinary Firebase password-provider ID tokens are accepted without email
verification to preserve immediate registration-to-Home behavior. All ID tokens
still undergo signature/expiry/revocation/disabled-account checks.

Existing email-link/custom accounts have no password until one is set: use Forgot
password? and Firebase's hosted reset email action. This keeps the same UID and
Firestore data. No user/data migration or password database is introduced. No
reset emails to real users were sent as part of automated tests.

Verification: 15 Firebase emulator/browser tests and 31 existing PostgreSQL/auth
tests passed, including password confirmation, duplicate accounts, wrong
credentials, standard reset, existing passwordless UID preservation, profile and
accessibility loading, logout and Save Event regressions. Local test URL remains
http://localhost:8451/; the built preview uses http://localhost:8003/.

Files changed for password auth: frontend/src/App.tsx, frontend/src/firebase.ts,
firebase_runtime.py, api.py, firestore_store.py, test_firebase.py,
test_firebase_browser.py, and this document. No Save Event, Previous Events,
workspace/result, presentation, prompts/research, polling, styling, or PostgreSQL
modules changed for this authentication update.

Live follow-up: real Firebase password signup, logout, password login and saved
preferences were verified with temporary accounts, then cleaned up. Captured
Accessly API payloads contained neither password fields nor the generated password;
Firestore profile fields contained no password. A first live follow-up assertion
failed; a subsequent staged run passed signup/logout/login/preferences. No real
password-reset email was sent; reset completion and passwordless UID retention
were verified in isolated emulators.


## Replacement Firebase project (2026-10-27)

The replacement Spark project is `accey-demo` (Accessly Demo). Its web app is
Accessly Web, app ID `1:1090447780261:web:b2a336d19a43b3086be04c`.
Email/Password is enabled. Firestore Standard uses `europe-west2`, with browser
reads/writes denied. Authorized domains include `accessly-murex.vercel.app`,
`localhost`, and `127.0.0.1`. No billing upgrade or paid backups were enabled.

Set all `VITE_FIREBASE_*` fields in `frontend/.env.example` together using the
new web app configuration; keep `VITE_IDENTITY_PROVIDER=firebase`. On Vercel,
keep `VITE_API_BASE_URL` pointed at the Northflank HTTPS URL ending in `/api`,
then rebuild. Local `.env.local` uses a separate backend on port 8001 for testing.

Northflank must use `ACCESSLY_IDENTITY_PROVIDER=firebase`,
`FIREBASE_PROJECT_ID=accey-demo`, and `GOOGLE_APPLICATION_CREDENTIALS` pointing
to a mounted **new-project** Admin service-account key. Keep this key out of
frontend variables, Git, Docker build context, and logs. Retain the old project
and key for rollback; existing accounts and data are not automatically migrated.

Password resets use the Firebase-hosted reset page without a continue URL.
A successful reset API response does not establish inbox delivery. Verify an
actual reset email and password change with an account you control before
claiming the delivery issue is solved.
