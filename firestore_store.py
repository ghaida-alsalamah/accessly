"""UID-scoped Firestore persistence preserving Accessly's public contracts."""
import hashlib
import os
import re
from datetime import datetime, timezone
from fastapi import HTTPException
from firebase_runtime import app
from db import OVERALL_STATUSES, NEED_STATUSES


def client():
    from firebase_admin import firestore
    return firestore.client(app=app())


def _user(uid):
    if not isinstance(uid, str) or not uid or '/' in uid:
        raise ValueError('A verified Firebase UID is required.')
    return client().collection('users').document(uid)


def default_user_id():
    uid = os.getenv('DEFAULT_FIREBASE_UID')
    if not uid:
        raise RuntimeError('DEFAULT_FIREBASE_UID is required for direct CLI use.')
    return uid


def _need_id(name):
    return hashlib.sha256(name.encode()).hexdigest()


def register_user(name, email, language, needs):
    """Create an unverified Auth identity without sending mail or creating a session."""
    from firebase_admin import auth
    try:
        user = auth.create_user(email=email, display_name=name, email_verified=False, app=app())
    except auth.EmailAlreadyExistsError:
        raise HTTPException(409, 'This email is already registered. Log in instead.') from None
    # Never overwrite an existing profile through the unauthenticated signup route.
    # A partial failure leaves the Auth user intact; authenticated recovery below
    # allows the email owner to finish onboarding instead of deleting their identity.
    ref = _user(user.uid)
    batch = client().batch()
    batch.create(ref, {'user_name': name, 'user_email': email, 'preferred_language': language,
                       'privacy_consent': True, 'consent_date': datetime.now(timezone.utc)})
    for order, need in enumerate(needs):
        batch.create(ref.collection('needs').document(_need_id(need)),
                     {'need_name': need, 'is_custom': need.startswith('Other:'), 'is_active': True, 'order': order})
    batch.commit()
    return user.uid


def complete_profile(uid, name, language, needs=None):
    """Authenticated recovery for a sign-in-created or partially registered account."""
    from google.cloud import firestore
    from firebase_admin import auth
    email = auth.get_user(uid, app=app()).email
    ref = _user(uid)
    @firestore.transactional
    def write(tx):
        if not ref.get(transaction=tx).exists:
            tx.create(ref, {'user_name': name, 'user_email': email, 'preferred_language': language,
                            'privacy_consent': True, 'consent_date': datetime.now(timezone.utc)})
            for order, need in enumerate(needs or []):
                tx.create(ref.collection('needs').document(_need_id(need)),
                          {'need_name': need, 'is_custom': need.startswith('Other:'), 'is_active': True, 'order': order})
    write(client().transaction())
    return get_user_profile(uid)


def get_user_profile(uid):
    ref = _user(uid)
    row = ref.get()
    if not row.exists:
        return None
    data = row.to_dict()
    needs = sorted((n.to_dict() for n in ref.collection('needs').stream()), key=lambda n: n.get('order', 0))
    # Keep email and Auth credentials out of agent context.
    return {'name': data['user_name'], 'preferred_language': data['preferred_language'],
            'needs': [n['need_name'] for n in needs if n.get('is_active')]}


def set_preferred_language(uid, language):
    _user(uid).update({'preferred_language': language})


def save_user_needs(uid, needs):
    from google.cloud import firestore
    ref = _user(uid)
    @firestore.transactional
    def write(tx):
        if not ref.get(transaction=tx).exists:
            raise HTTPException(404, 'User not found.')
        old = list(ref.collection('needs').stream(transaction=tx))
        for row in old:
            if row.to_dict()['need_name'] not in needs:
                tx.update(row.reference, {'is_active': False})
        for order, name in enumerate(needs):
            tx.set(ref.collection('needs').document(_need_id(name)),
                   {'need_name': name, 'is_custom': name.startswith('Other:'), 'is_active': True, 'order': order})
    write(client().transaction())


def _request_ref(uid, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r'REQ-[0-9]+', request_id):
        return None
    return _user(uid).collection('requests').document(request_id)


def _present(row):
    record = row.to_dict()
    return {key: record.get(key) for key in ('request_id', 'event_name', 'event_url', 'organizer_email', 'email_subject', 'status', 'accommodations')}


def list_requests(uid):
    return [_present(r) for r in sorted(_user(uid).collection('requests').stream(), key=lambda r: int(r.id[4:]))]


def get_request(uid, request_id):
    ref = _request_ref(uid, request_id)
    if ref is None:
        return None
    row = ref.get()
    return _present(row) if row.exists else None


def create_request(uid, event_name, event_url, organizer_email, email_subject):
    from google.cloud import firestore
    ref = _user(uid)
    counter = client().collection('_accessly_counters').document('requests')
    @firestore.transactional
    def write(tx):
        if not ref.get(transaction=tx).exists:
            return None
        needs = [n for n in ref.collection('needs').stream(transaction=tx) if n.to_dict().get('is_active')]
        if not needs:
            return None
        count = counter.get(transaction=tx)
        number = (count.to_dict() or {}).get('value', 0) + 1
        request_id = f'REQ-{number:03d}'
        record = {'request_id': request_id, 'event_name': event_name, 'event_url': event_url,
                  'organizer_email': organizer_email, 'email_subject': email_subject,
                  'status': 'PENDING', 'accommodations': {n.to_dict()['need_name']: 'PENDING' for n in needs}}
        request = ref.collection('requests').document(request_id)
        tx.set(counter, {'value': number})
        tx.create(request, {**record, 'sent_at': datetime.now(timezone.utc)})
        for need in needs:
            tx.create(request.collection('request_needs').document(need.id),
                      {'need_name': need.to_dict()['need_name'], 'status': 'PENDING', 'last_notified_status': None})
        return record
    return write(client().transaction())


def update_request(uid, request_id, accommodation_statuses, overall_status=None):
    from google.cloud import firestore
    if overall_status is not None and overall_status not in OVERALL_STATUSES:
        raise ValueError('Unsupported overall request status.')
    if any(s not in NEED_STATUSES for s in accommodation_statuses.values()):
        raise ValueError('Unsupported accommodation status.')
    ref = _request_ref(uid, request_id)
    if ref is None:
        return None
    @firestore.transactional
    def write(tx):
        row = ref.get(transaction=tx)
        if not row.exists:
            return None
        record = _present(row)
        accommodations = dict(record['accommodations'])
        for name, status in accommodation_statuses.items():
            if name in accommodations:
                accommodations[name] = status
                tx.update(ref.collection('request_needs').document(_need_id(name)), {'status': status})
        record['accommodations'] = accommodations
        if overall_status is not None:
            record['status'] = overall_status
        tx.update(ref, {'status': record['status'], 'accommodations': accommodations})
        return record
    return write(client().transaction())


def delete_user(uid):
    # Firestore does not cascade subcollections. Removing Auth first prevents
    # subsequent writes; recursive_delete is retryable if cleanup is interrupted.
    from firebase_admin import auth
    ref = _user(uid)
    if not ref.get().exists:
        return False
    try:
        auth.delete_user(uid, app=app())
    except auth.UserNotFoundError:
        pass
    client().recursive_delete(ref)
    return True
