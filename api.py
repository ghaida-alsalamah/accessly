"""FastAPI adapter; optional isolated public-demo mode. Agent logic remains in main.py."""
import logging
import os
import runpy
import threading
import sys

# Agent streaming output includes Unicode; Windows redirected consoles may use cp1252.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4
from result_presenter import format_result, unavailable
import contextvars
import auth
import db
import mailer
from deployment_runtime import PUBLIC, OWNER, ORIGINS, current_user_id, reserve_action, require_public_url, configure_agent, authorize_approval
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, HttpUrl

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
# The middleware does the real JWT check; this only adds the Authorize button to /docs.
app = FastAPI(title="Accessly API", dependencies=[Depends(HTTPBearer(auto_error=False))])
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "Authorization"])
lock = threading.RLock()
worker = ThreadPoolExecutor(max_workers=1)
sessions = {}
jobs = {}
session_context = {}

@app.middleware("http")
async def user_session(request: Request, call_next):
    path = request.url.path
    protected = path.startswith(("/api/", "/requests/", "/jobs/")) or path in ("/profile", "/chat", "/requests")
    if not protected or request.method == "OPTIONS" or path in ("/api/health", "/health") or path.startswith("/api/auth/"):
        return await call_next(request)
    try:
        user_id = auth.user_from_header(request.headers.get("Authorization"))
    except HTTPException as error:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)
    token = OWNER.set(str(user_id))
    try:
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        OWNER.reset(token)

def owned_session(session_id):
    if session_id not in sessions or session_context.get(session_id, {}).get("owner") != OWNER.get():
        raise HTTPException(404, "Conversation expired or unavailable. Analyze the event again.")

def owned_job(job_id):
    if job_id not in jobs:
        raise HTTPException(404, "Action not found")
    owned_session(jobs[job_id]["session_id"])
    return jobs[job_id]

def visitor_busy():
    return any(j["status"] == "processing" and session_context.get(j["session_id"], {}).get("owner") == OWNER.get() for j in jobs.values())

class Profile(BaseModel):
    needs: list[Annotated[str, Field(max_length=1000)]] = Field(min_length=1, max_length=30)  # needs.need_name is VARCHAR(1000)

class Event(BaseModel):
    url: HttpUrl

class Message(BaseModel):
    message: str = Field(min_length=1, max_length=12000)

class Register(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    preferred_language: Literal["ar", "en"]
    consent: bool = Field(strict=True)

class OtpRequest(BaseModel):
    email: EmailStr

class Language(BaseModel):
    preferred_language: Literal["ar", "en"]

class OtpVerify(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


def user_profile():
    profile = db.get_user_profile(current_user_id())
    if profile is None:
        raise HTTPException(404, "User not found.")
    return profile

def saved_needs():
    return user_profile()["needs"]

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/auth/register", status_code=201)
@app.post("/api/auth/register", status_code=201)
def register(body: Register):
    if not body.consent:
        raise HTTPException(422, "Privacy consent is required to create an account.")
    email = body.email.lower()
    if len(email) > 100:  # users.user_email is VARCHAR(100)
        raise HTTPException(422, "Email must be at most 100 characters.")
    user_id = db.create_user(body.name.strip(), email, body.preferred_language)
    if user_id is None:
        raise HTTPException(409, "This email is already registered. Log in instead.")
    return {"user_id": user_id}

@app.post("/auth/send-otp")
@app.post("/api/auth/send-otp")
def send_otp(body: OtpRequest):
    # Same answer whether or not the email exists, so it can't be used to find accounts.
    response = {"detail": "If this email is registered, a code was sent. You can request a new one after 60 seconds."}
    email = body.email.lower()
    code = auth.new_otp()
    language = db.store_otp(email, auth.hash_otp(code))
    if language is not None:
        subject, text = auth.otp_email(language, code)
        try:
            mailer.send_test_mode_email(email, subject, text)
        except Exception:
            logging.exception("Login code email failed")
    return response

@app.post("/auth/verify-otp")
@app.post("/api/auth/verify-otp")
def verify_otp(body: OtpVerify):
    user_id = db.verify_otp(body.email.lower(), auth.hash_otp(body.code))
    if user_id is None:
        raise HTTPException(401, "Invalid or expired code.")
    return {"access_token": auth.create_token(user_id), "token_type": "bearer"}

@app.get("/profile")
@app.get("/api/profile")
def profile():
    with lock:
        return user_profile()

@app.post("/profile")
@app.post("/api/profile")
@app.put("/api/profile")
def save_profile(body: Profile):
    with lock:
        if visitor_busy():
            raise HTTPException(409, "Wait for the active agent action before changing preferences.")
        needs = list(dict.fromkeys(n.strip() for n in body.needs if n.strip()))
        if not needs:
            raise HTTPException(422, "Select at least one accessibility need.")
        user_profile()  # 404 before writing if the user doesn't exist
        db.save_user_needs(current_user_id(), needs)
        return user_profile()

@app.put("/api/profile/language")
def save_language(body: Language):
    user_profile()  # 404 if the user doesn't exist
    db.set_preferred_language(current_user_id(), body.preferred_language)
    return user_profile()

@app.delete("/api/account", status_code=204)
def delete_account():
    """Delete the logged-in user's account and all their data (PDPL right to deletion)."""
    with lock:
        if visitor_busy():
            raise HTTPException(409, "Wait for the active agent action before deleting your account.")
        if not db.delete_user(current_user_id()):
            raise HTTPException(404, "User not found.")
        # Drop their in-memory conversations too; those hold their needs and event results.
        for session_id in [s for s, c in session_context.items() if c.get("owner") == OWNER.get()]:
            session_context.pop(session_id, None)
            sessions.pop(session_id, None)
        for job_id in [j for j, job in jobs.items() if job["session_id"] not in sessions]:
            jobs.pop(job_id)

@app.get("/requests")
@app.get("/api/requests")
def requests():
    with lock:
        return db.list_requests(current_user_id())


def submit(session_id, message):
    with lock:
        if visitor_busy():
            raise HTTPException(409, "An agent action is already running. Please wait.")
        if PUBLIC and sum(j["status"] == "processing" for j in jobs.values()) >= 8:
            raise HTTPException(429, "The demo queue is full. Please try again shortly.")
        reserve_action()
        job_id = str(uuid4())
        jobs[job_id] = {"id": job_id, "session_id": session_id, "status": "processing", "response": ""}
    context = session_context.setdefault(session_id, {"url": None, "needs": saved_needs(), "result": None, "owner": OWNER.get(), "reference": session_id[:12]})
    def execute():
        try:
            if sessions[session_id] is None:
                namespace = runpy.run_path(str(ROOT / "main.py"))
                sessions[session_id] = namespace["agent"]
                configure_agent(namespace, context)
            authorize_approval(message, context)
            if PUBLIC:
                result = sessions[session_id](message, limits={"turns": 20, "total_tokens": 160000})
            else:
                result = sessions[session_id](message)
            with lock:
                jobs[job_id]["response"] = str(result)
            present_job(job_id)
        except Exception:
            logging.exception("Agent action failed")
            with lock:
                jobs[job_id].update(status="failed", response="The agent action failed. Check the backend terminal for details. No automatic retry was made.")
        finally:
            if PUBLIC and context.get("browser"):
                try:
                    context["browser"]._cleanup()
                except Exception:
                    logging.exception("Browser cleanup failed")
    worker.submit(contextvars.copy_context().run, execute)
    return dict(jobs[job_id])

def present_job(job_id):
    job = jobs[job_id]
    context = session_context[job["session_id"]]
    try:
        result = format_result(job["response"], context["needs"], context["url"], sessions[job["session_id"]].model, context["result"])
        result["requests"] = [r for r in db.list_requests(current_user_id()) if r.get("event_url", "").rstrip("/") == (context["url"] or "").rstrip("/")]
        context["result"] = result
    except Exception:
        logging.exception("Presentation failed for job %s; agent action will not be repeated", job_id)
        result = unavailable()
    with lock:
        job.update(status="completed", result=result)

@app.post("/api/jobs/{job_id}/presentation", status_code=202)
def retry_presentation(job_id: str):
    with lock:
        job = owned_job(job_id)
        if not job or not job.get("response") or job["status"] == "failed":
            raise HTTPException(404, "No completed agent response to format.")
        if visitor_busy():
            raise HTTPException(409, "An action is still running. Please wait.")
        reserve_action()
        job["status"] = "processing"
        worker.submit(contextvars.copy_context().run, present_job, job_id)
        return dict(job)

@app.post("/api/events", status_code=202)
def analyze(body: Event):
    if PUBLIC:
        try:
            require_public_url(str(body.url))
        except (ValueError, OSError):
            raise HTTPException(422, "Use a publicly accessible HTTP(S) event URL.")
    session_id = str(uuid4())
    with lock:
        if len(sessions) >= 100:
            raise HTTPException(409, "Restart the local backend to clear old conversations.")
        sessions[session_id] = None
        session_context[session_id] = {"url": str(body.url), "needs": saved_needs(), "result": None, "owner": OWNER.get(), "reference": session_id[:12]}
    prompt = "Check this event: " + str(body.url)
    if PUBLIC:
        prompt += "\nPublic demonstration: browse in read-only mode using navigate and get_text. Never submit a form. Include [Accessly " + session_id[:12] + "] in every email draft subject. Email is test-inbox only; wait for exact approval."
    return submit(session_id, prompt)

@app.post("/api/sessions/{session_id}/messages", status_code=202)
def message(session_id: str, body: Message):
    owned_session(session_id)
    return submit(session_id, body.message)

@app.post("/requests/{request_id}/check", status_code=202)
@app.post("/api/requests/{request_id}/check", status_code=202)
def check_reply(request_id: int):
    record = db.get_request(current_user_id(), request_id)
    if record is None:
        raise HTTPException(404, "Request not found")
    session_id = str(uuid4())
    sessions[session_id] = None
    session_context[session_id] = {"url": record.get("event_url"), "needs": list(record.get("accommodations", {})), "result": None, "owner": OWNER.get(), "reference": session_id[:12]}
    return submit(session_id, "Check reply for " + request_id)

@app.get("/jobs/{job_id}")
@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    with lock:
        return dict(owned_job(job_id))

class Chat(BaseModel):
    url: HttpUrl | None = None
    session_id: str | None = None
    message: str | None = Field(default=None, min_length=1, max_length=12000)

@app.post("/chat", status_code=202)
@app.post("/api/chat", status_code=202)
def chat(body: Chat):
    if body.session_id and body.message and body.url is None:
        return message(body.session_id, Message(message=body.message))
    if body.url is not None and body.session_id is None and body.message is None:
        return analyze(Event(url=body.url))
    raise HTTPException(422, "Provide url for a new event, or session_id and message for a follow-up.")

# Temporary page for testing the database flow by hand; not the final design.
# The Dockerfiles don't copy test_page.html, so it 404s in production.
# English is Privacy_Policy.md, Arabic is Privacy_Policy_ar.md (same for terms).
POLICY_FILES = {"privacy": "Privacy_Policy", "terms": "Terms_And_Conditions"}
MISSING_POLICY = {"en": "{} hasn't been written yet.", "ar": "لم تتم كتابة {} بعد."}

@app.get("/test", include_in_schema=False)
def test_page():
    if not (ROOT / "test_page.html").is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(ROOT / "test_page.html", headers={"Cache-Control": "no-store"})  # always serve the latest edit

@app.get("/test/policy/{doc}/{lang}", include_in_schema=False)
def test_policy(doc: str, lang: str):
    if doc not in POLICY_FILES or lang not in MISSING_POLICY:
        raise HTTPException(404, "Not found")
    name = POLICY_FILES[doc] + ("_ar" if lang == "ar" else "") + ".md"
    if not (ROOT / name).is_file():
        return PlainTextResponse(MISSING_POLICY[lang].format(name), status_code=404)
    return FileResponse(ROOT / name, media_type="text/plain; charset=utf-8")

# Production UI is mounted after API routes.
if (ROOT / "frontend" / "dist").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True), name="frontend")
