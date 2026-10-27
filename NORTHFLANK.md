# Northflank remote Docker build

No deployment performed. Existing Dockerfile includes frontend; use the new
backend-only Dockerfile.northflank. Frontend and main.py are unchanged.

## Build and networking

Choose Dockerfile build (BuildKit), not buildpacks. Repository root build context
(`/`), Dockerfile path `/Dockerfile.northflank`. No Node or Windows runtime needed.
Leave the command override empty; image CMD runs:

    sh -c 'exec python -m uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1'

Set PORT=8000. Expose internal port 8000 as public HTTP in Northflank, which
provides public HTTPS on 443. Health/readiness: HTTP GET /health on port 8000.
Use one replica and one worker for JSON and in-memory conversation/job state.

## Runtime environment (never build arguments)

Required values to provide:
- AWS_BEARER_TOKEN_BEDROCK: backend secret
- AWS_REGION: eu-north-1 (also the image default)
- ACCESSLY_EMAIL: Gmail sender
- ACCESSLY_EMAIL_APP_PASSWORD: backend secret
- ACCESSLY_TEST_RECIPIENT: controlled test inbox, never a real organizer
- ACCESSLY_ALLOWED_ORIGINS: exact production frontend HTTPS origin; comma-separated
  if multiple origins. No wildcard. Must be supplied before public-mode startup.

Image defaults (set these explicitly in the dashboard if desired):
- PORT=8000
- ACCESSLY_PUBLIC_MODE=1
- ACCESSLY_DATA_DIR=/var/data/accessly
- STRANDS_BROWSER_HEADLESS=true
- PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
- PYTHON_DOTENV_DISABLED=1 (disables dotenv even in unchanged agent code)

Optional application quota settings:
- ACCESSLY_DAILY_ACTION_LIMIT=60
- ACCESSLY_VISITOR_DAILY_LIMIT=12

Do not add secrets to VITE variables, Docker ARG, Git, or frontend configuration.
.env is ignored by Git and excluded by the Docker build allowlist.
The image installs Playwright Chromium and Linux dependencies explicitly and
runs as the non-root accessly user. Container smoke test makes no model/email calls.

## API compatibility

Existing frontend /api endpoints remain. Public-mode data routes require the
existing visitor header: Authorization: Bearer followed by 64 lowercase hex chars.
Health routes are unauthenticated.

- GET /health and /api/health -> {"status":"ok"}
- GET /profile and /api/profile
- POST /profile or /api/profile, existing PUT /api/profile; body {"needs":["Captions"]}
- POST /chat or /api/chat: new event {"url":"https://official-event-url"}
- POST /chat follow-up: {"session_id":"returned-session-id","message":"Draft only"}
- Chat returns HTTP 202 job object. Poll GET /jobs/{id} or /api/jobs/{id} for
  completion and structured result. No new synchronous agent implementation.
- GET /requests and /api/requests
- POST /requests/{request_id}/check and /api/requests/{request_id}/check
- Existing /api/events, /api/sessions/{id}/messages and presentation retry remain.

## Local verification

Seven Python route/result tests passed. On the Windows host, container_smoke.py
passed actual FastAPI startup, /health, Strands imports and headless Chromium.
This is NOT a Linux container test. Local Docker is unavailable and is NOT a
prerequisite. Build Dockerfile.northflank remotely from GitHub using Northflank.
Inspect build logs for dependency installation and runtime logs for startup.
After startup, use the Northflank container console to run:

    python container_smoke.py

This checks Linux Chromium and imports inside the actual image without sending
email or calling Bedrock. Its temporary FastAPI server uses port 8765.

Optional commands for any other machine with Docker:

    docker build -f Dockerfile.northflank -t accessly-backend:northflank .
    docker run --rm --init accessly-backend:northflank python container_smoke.py

The smoke test creates isolated temporary storage and uses an invalid controlled
inbox placeholder, without sending mail or calling Bedrock. For normal startup,
pass the required runtime settings using a local ignored env file with docker's
--env-file option and publish -p 8000:8000. Do not publish that env file.

## Storage and remaining risks

No migration was made. The profile/request JSON files and quota SQLite database
remain on local disk. Northflank ephemeral data is lost on restart/termination;
/var/data/accessly is only a directory, not an automatically provisioned volume.
Conversation/job state is in memory and also expires on restart.
https://northflank.com/docs/v1/application/scale/increase-storage
https://northflank.com/docs/v1/application/network/configure-ports

Not yet tested: Linux image build/dependency availability, Linux Chromium launch,
container memory usage, Northflank SMTP/IMAP, or public end-to-end flow. Do not
claim runtime verification before checking the remote build, deployed /health,
container smoke test and deployment logs. Local Docker Desktop is not required.


## Selective database/auth integration

The current frontend and event/research pipeline are retained. User profiles and
request records now use PostgreSQL; protected API routes require a JWT in both
local and public modes. Health and registration/OTP routes remain public.
The former random visitor token is not a login credential.

Required new backend environment variables:

- `DATABASE_URL`: PostgreSQL connection URI, including the provider's TLS options.
- `JWT_SECRET`: at least 32 random characters; used for JWT signing and OTP hashing.
- `DEFAULT_USER_ID`: only for direct terminal use of `main.py`; must identify an
  existing user. API requests derive ownership solely from the verified JWT.

Keep `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `FIRECRAWL_API_KEY`, and the existing
Gmail/test-recipient, CORS, browser, data-directory and quota configuration.
`.env.production.example` documents the variable names. No secrets belong in
frontend/VITE variables. Local API startup loads the root `.env`; containers with
`PYTHON_DOTENV_DISABLED=1` require runtime environment settings instead.

No database or tables are created at startup. Before enabling the integrated
workflow, provision a separate PostgreSQL database and user, inspect any existing
tables, and apply the reviewed schema explicitly. With `DATABASE_URL` already
exported in the shell, the later, separately authorized command is:

```bash
psql -X --dbname="$DATABASE_URL" --set=ON_ERROR_STOP=1 --single-transaction --file=schema.sql
```

This command is not run by the application or Docker build. `IF NOT EXISTS` does
not upgrade existing tables. Existing JSON profiles/requests are not imported or
deleted; a later import needs explicit user ownership mapping.

After schema setup, install `requirements-production.txt` in the intended backend
environment and start the existing Uvicorn command. Registration uses the existing
three-step UI, followed by email-code verification in Login. Registration alone
returns a user ID, not a token. Preferences are saved only after verification;
existing users load their saved preferences after Login. New registrations use
English as the explicit default preferred language.

OTP email delivery intentionally remains TEST MODE: every code goes to
`ACCESSLY_TEST_RECIPIENT`, with the intended user's email identified in the body.
The generic send-code response does not confirm successful delivery; failures are
logged. Codes expire after five minutes, have a 60-second resend cooldown, and
allow five wrong guesses. JWTs last seven days; there is no refresh-token or
server-side revocation endpoint. Frontend logout clears its token and only
Accessly conversation caches, then returns to Intro.

The database uses integer request primary keys internally. API and agent tools
continue exposing `REQ-001`-style strings and the existing accommodations/job/result
structures. Existing browser research, send approvals, email thread matching,
formatting retries, result presentation and polling are preserved. Job and agent
sessions are still in memory and expire when the backend restarts. SQLite quota
storage still needs a persistent `ACCESSLY_DATA_DIR` in public mode.

The added `test_auth.py` uses mocked database connections and rejects any real
`psycopg.connect()` attempt. Run it with test-only secrets and dotenv disabled to
avoid loading local credentials. Legacy tests that assume anonymous visitor
headers or patch the JSON API storage helper need separate fixture updates for
JWT-backed storage. No live PostgreSQL, email or model service is needed by the
new auth/storage tests.
