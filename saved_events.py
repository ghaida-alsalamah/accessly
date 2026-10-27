"""Explicit Firestore snapshots of completed jobs; never invokes the agent."""
import hashlib
import json
import logging
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
import firebase_runtime
from deployment_runtime import current_user_id


class ConversationTurn(BaseModel):
    role: Literal['user', 'agent']
    text: str = Field(max_length=12000)


class SaveEvent(BaseModel):
    job_id: str = Field(min_length=1, max_length=100)
    conversation: list[ConversationTurn] = Field(default_factory=list, max_length=100)


def collection(uid):
    from firebase_admin import firestore
    if not isinstance(uid, str) or not uid or '/' in uid:
        raise ValueError('A Firebase UID is required.')
    return firestore.client(app=firebase_runtime.app()).collection('users').document(uid).collection('saved_events')


def save_snapshot(uid, snapshot):
    from google.cloud import firestore
    ref = collection(uid).document(hashlib.sha256(snapshot['job_id'].encode()).hexdigest())
    @firestore.transactional
    def write(tx):
        existing = ref.get(transaction=tx)
        if existing.exists:
            return {'id': ref.id, 'saved': True}
        tx.create(ref, {**snapshot, 'saved_at': datetime.now(timezone.utc)})
        return {'id': ref.id, 'saved': True}
    from firebase_admin import firestore
    return write(firestore.client(app=firebase_runtime.app()).transaction())


def list_saved(uid):
    from google.cloud import firestore
    rows = collection(uid).order_by('saved_at', direction=firestore.Query.DESCENDING).limit(100).stream()
    return [{'id': row.id, **{key: row.to_dict().get(key) for key in ('event_name', 'event_url', 'status', 'saved_at')}} for row in rows]


def get_saved(uid, event_id):
    if not re.fullmatch(r'[a-f0-9]{64}', event_id):
        raise HTTPException(404, 'Saved event not found.')
    row = collection(uid).document(event_id).get()
    if not row.exists:
        raise HTTPException(404, 'Saved event not found.')
    return {'id': row.id, **row.to_dict()}


def install_routes(app, owned_job, session_context, lock):
    def owner():
        if not firebase_runtime.enabled():
            raise HTTPException(409, 'Saved events require Firebase sign-in.')
        return current_user_id()

    @app.post('/api/saved-events')
    def save_event(body: SaveEvent):
        uid = owner()
        with lock:
            job = owned_job(body.job_id)
            result = job.get('result')
            if job['status'] != 'completed' or not result or result.get('presentation_status') != 'ready':
                raise HTTPException(409, 'Wait until the completed result is displayed before saving.')
            context = session_context[job['session_id']]
            if not context.get('url'):
                raise HTTPException(409, 'Only a completed event analysis can be saved.')
            snapshot = deepcopy({
                'schema_version': 1, 'job_id': job['id'], 'session_id': job['session_id'],
                'event_url': context['url'], 'event_name': (result.get('event') or {}).get('name') or context['url'],
                'status': job['status'], 'result': result, 'response': job.get('response', ''),
                'needs': context['needs'], 'conversation': [turn.model_dump() for turn in body.conversation],
            })
        if len(json.dumps(snapshot, ensure_ascii=False).encode()) > 800_000:
            raise HTTPException(422, 'This result is too large to save. Your current result remains available.')
        try:
            return save_snapshot(uid, snapshot)
        except Exception:
            logging.exception('Could not save completed event snapshot')
            raise HTTPException(503, 'Could not save the event. Please try again.') from None

    @app.get('/api/saved-events')
    def saved_events():
        uid = owner()
        try:
            return list_saved(uid)
        except Exception:
            logging.exception('Could not list saved events')
            raise HTTPException(503, 'Could not load saved events. Please try again.') from None

    @app.get('/api/saved-events/{event_id}')
    def saved_event(event_id: str):
        uid = owner()
        try:
            return get_saved(uid, event_id)
        except HTTPException:
            raise
        except Exception:
            logging.exception('Could not read saved event')
            raise HTTPException(503, 'Could not open the saved event. Please try again.') from None
