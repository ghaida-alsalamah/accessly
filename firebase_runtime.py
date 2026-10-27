"""Lazy Firebase Admin setup; no credentials are printed or read by the browser."""
import os
from functools import lru_cache
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()


def enabled():
    provider = os.getenv('ACCESSLY_IDENTITY_PROVIDER', 'postgres')
    if provider not in ('postgres', 'firebase'):
        raise RuntimeError('ACCESSLY_IDENTITY_PROVIDER must be postgres or firebase.')
    return provider == 'firebase'


@lru_cache(maxsize=1)
def app():
    import firebase_admin
    project = os.getenv('FIREBASE_PROJECT_ID')
    if not project:
        raise RuntimeError('FIREBASE_PROJECT_ID is required for Firebase.')
    # Application Default Credentials honors GOOGLE_APPLICATION_CREDENTIALS.
    # Emulators use no service-account key.
    if os.getenv('FIRESTORE_EMULATOR_HOST') and os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
        from google.auth.credentials import AnonymousCredentials
        from firebase_admin import credentials
        class EmulatorCredential(credentials.Base):
            def get_credential(self):
                return AnonymousCredentials()
        return firebase_admin.initialize_app(EmulatorCredential(), {'projectId': project}, name='accessly')
    return firebase_admin.initialize_app(options={'projectId': project}, name='accessly')


def registration_token(uid):
    """Called only for a just-created UID, after its profile batch commits."""
    from firebase_admin import auth
    return auth.create_custom_token(uid, {'accessly_registration': True}, app=app()).decode('utf-8')


def user_from_header(header):
    from firebase_admin import auth
    if not header or not header.startswith('Bearer '):
        raise HTTPException(401, 'Log in first.')
    try:
        claims = auth.verify_id_token(header[7:], app=app(), check_revoked=True)
        uid = claims['uid']
        if not isinstance(uid, str) or not uid or '/' in uid:
            raise ValueError('A valid identity is required.')
        if claims.get('accessly_registration') is True:
            # A new signup may enter its own account without claiming email
            # ownership. Once the email owner verifies, reject the old signup
            # session, including any refreshes/custom-token replays.
            if (claims.get('firebase', {}).get('sign_in_provider') != 'custom'
                    or auth.get_user(uid, app=app()).email_verified):
                raise ValueError('Use verified email-link login for this account.')
        elif claims.get('firebase', {}).get('sign_in_provider') == 'password':
            pass  # Firebase has authenticated the password; verification email is not required.
        elif not claims.get('email_verified'):
            raise ValueError('An email-verified identity is required.')
        return uid
    except (auth.InvalidIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError, auth.UserNotFoundError, ValueError, KeyError):
        raise HTTPException(401, 'Invalid or expired login. Log in again.') from None
