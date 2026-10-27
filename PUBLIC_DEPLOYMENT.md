# Public HTTPS deployment of the current Firebase app

Status: deployment preparation only. No public service or domain has been created.
Hosting-account access is required before publishing. Local development and Neon
are left intact. This guide deliberately uses the existing app and root Dockerfile.

## Service and image

Use one combined frontend/backend container built with **/Dockerfile**, context `/`.
Do not use Dockerfile.northflank for this combined deployment: it is backend-only.
The current working application must be supplied to the build; the remote main
branch may not include the uncommitted Firebase/UI work. Never deploy stale main
or commit local secrets just to trigger a remote build.

Build argument:

```
VITE_IDENTITY_PROVIDER=firebase
```

Leave VITE_FIREBASE_AUTH_CONTINUE_URL unset to use the existing window.location.origin
fallback: email links then return to the public HTTPS origin that requested them.
Alternatively set it explicitly to the final public URL with a trailing slash.
Never put a localhost URL in the production build. VITE_* values are public bundle
configuration, not a place for private keys, AWS credentials or SMTP passwords.
The existing Firebase web-app configuration is public browser configuration.

Expose container HTTP port 8000 through the hosting platform's managed HTTPS ingress.
Use GET /health for readiness. Use one worker and one replica, disable scale-to-zero
and request timeout/CPU suspension settings that would interrupt background agent
jobs. Jobs/conversations remain in memory exactly as in the current app, so a
restart loses active jobs; Firestore saved events/preferences remain persisted.

## Runtime environment and secrets

Set these in the hosting platform's runtime configuration, not build arguments:

```
PORT=8000
ACCESSLY_IDENTITY_PROVIDER=firebase
FIREBASE_PROJECT_ID=accey-80215
GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase-admin.json
PYTHON_DOTENV_DISABLED=1
ACCESSLY_DATA_DIR=/var/data/accessly
ACCESSLY_ALLOWED_ORIGINS=https://FINAL_PUBLIC_HOST
ACCESSLY_PUBLIC_MODE=0
```

ACCESSLY_PUBLIC_MODE=0 explicitly preserves the currently tested local Firebase
agent behavior. The image default is 1, a pre-existing public-demo mode that changes
agent prompts/tools and applies demo limits. Do not silently turn that on while
claiming to preserve the exact current agent workflow. No application code is
changed by this deployment choice.

Mount the existing Firebase service-account JSON as a runtime **secret file** at
/run/secrets/firebase-admin.json, readable by container UID 10001. Do not copy it
into Git, the image, a build argument, frontend assets or logs. Do not use the Mac
/Users/... path in production. An alternative on Google Cloud is an appropriately
permissioned attached runtime service account/ADC, without a JSON key mount.

Securely transfer the currently used runtime values without printing them:

- AWS_BEARER_TOKEN_BEDROCK
- AWS_REGION
- FIRECRAWL_API_KEY
- ACCESSLY_EMAIL
- ACCESSLY_EMAIL_APP_PASSWORD
- ACCESSLY_TEST_RECIPIENT

Keep the Gmail configuration because agent accommodation mail/reply handling is
separate from Firebase login. Do not change recipients or mail behavior during
deployment. Keep DATABASE_URL/JWT_SECRET in the existing fallback setup; do not
change Neon, run schemas, migrate rows or remove PostgreSQL code. Firebase runtime
does not need to use those PostgreSQL secrets.

Never set FIRESTORE_EMULATOR_HOST, FIREBASE_AUTH_EMULATOR_HOST or
VITE_FIREBASE_AUTH_EMULATOR_URL in a public deployment.

## Firebase authorized domain

After the platform assigns the final HTTPS domain:

1. Add its hostname to Firebase Authentication > Settings > Authorized domains.
2. Preserve existing authorized domains, including localhost for development.
3. Verify the production bundle's continue URL resolves to that public HTTPS origin.
4. Do not change Auth providers, custom-token registration, Firestore schema or rules
   as part of deployment. Browser Firestore access should remain denied; backend
   service-account IAM supplies the existing Firestore access.

## Required checks before reporting success

- Check the remote image build and container startup, including Chromium support.
- Fetch the HTTPS URL and /health from an external network, not just localhost.
- Check the rendered app has the existing UI and no credentials/private-key content.
- Create an explicitly temporary test account; verify direct signup to Home,
  preference editing and logout. Clean up only that test account.
- Verify real email-link sending and public return URL. API acceptance alone does
  not confirm inbox receipt; the previous inbox-delivery issue must remain explicit.
- Run one authorized real event analysis; confirm polling and result presentation.
- Save the completed event, verify toast/navigation, Previous Events and reopening
  without another agent run, and verify another UID cannot read it.
- Do not claim a physical second-device test unless someone actually performs it.

On Northflank, public ports receive managed HTTPS domains; upload the Admin JSON
as a runtime secret file and enter backend values in runtime secrets. The existing
all-in-one Dockerfile avoids a separate frontend/API origin configuration.

## Local preparation results

The existing root Dockerfile successfully built `accessly:firebase-deploy-check`
in Firebase mode on local Docker (Linux ARM64). An offline non-root container
smoke test passed API /health, frontend serving, saved-event route registration,
absence of local .env/Admin JSON/private keys in app assets, absence of the fixed
localhost:8451 test redirect, and Linux headless Chromium launch. No secrets were
supplied to the build or smoke test. A hosting-platform build on its target
architecture and external HTTPS/functionality checks are still required.

Publishing is blocked by missing hosting access: no Northflank/Render/Railway/
Koyeb token or Google Cloud deployment login was configured in this environment.
No public service/domain, DNS or Firebase authorized-domain change was made.
Only this deployment guide was added during preparation; application files,
local .env, development servers and PostgreSQL were not changed.

References:
- https://northflank.com/docs/v1/application/getting-started/build-and-deploy-your-code
- https://northflank.com/docs/v1/application/secure/upload-secret-files
- https://firebase.google.com/docs/auth/web/email-link-auth
