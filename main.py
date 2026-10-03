import os
from strands import Agent, tool
from strands_tools.browser import LocalChromiumBrowser
from datetime import date, datetime
import smtplib
import ssl
import unicodedata
import re
import html as html_lib
from copy import deepcopy
from email.message import EmailMessage
from email.utils import parseaddr
import imaplib
import email
from email.header import decode_header
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sent_requests = []
browser = LocalChromiumBrowser()

# Public event research contains no user-private data, so caching the same
# event URL avoids repeated Firecrawl calls within the same process.
_RESEARCH_EVENT_CACHE = {}

@tool
def research_event(event_url: str):
    """
    Research one event from the ORIGINAL event URL supplied by the user.

    Call this tool exactly once per event analysis. It already performs the
    event-page retrieval, relevant official-link inspection, and official-domain
    search fallback through Accessly's web retrieval layer.

    Do not call this tool again with links returned by this tool.
    """

    normalized_url = event_url.strip().rstrip("/")

    if normalized_url in _RESEARCH_EVENT_CACHE:
        cached = deepcopy(_RESEARCH_EVENT_CACHE[normalized_url])
        cached["cache_hit"] = True
        return cached

    try:
        from web_retrieval import research_event as retrieve_event
        result = retrieve_event(event_url)

        if isinstance(result, dict):
            result = deepcopy(result)
            result.setdefault("cache_hit", False)
            result["research_complete"] = result.get("status") == "success"
            result["tool_guidance"] = (
                "Event web research is complete for this URL. Do not call "
                "research_event again for links discovered in this result. "
                "Use the returned evidence. Use the browser only for an "
                "interactive form/page or when retrieval failed."
            )

            if result.get("status") == "success":
                _RESEARCH_EVENT_CACHE[normalized_url] = deepcopy(result)

        return result

    except Exception as e:
        return {
            "status": "failed",
            "event_url": event_url,
            "error_type": type(e).__name__,
            "error": str(e),
            "message": (
                "The event could not be researched with the primary "
                "web retrieval layer. Use the browser only as a fallback."
            )
        }


@tool
def check_event_timing(
    event_date: str,
    preferred_notice_days: int | None = None,
    event_end_date: str | None = None
):
    """
    Check an event's lifecycle and, when provided, its accommodation notice window.

    Args:
        event_date: Event start date in YYYY-MM-DD format.
        preferred_notice_days: Optional number of days of advance notice stated by
            the organizer. Pass None when no notice period is stated.
        event_end_date: Optional event end date in YYYY-MM-DD format for multi-day
            events.
    """

    start = datetime.strptime(event_date, "%Y-%m-%d").date()
    end = (
        datetime.strptime(event_end_date, "%Y-%m-%d").date()
        if event_end_date
        else start
    )

    if end < start:
        raise ValueError("event_end_date cannot be before event_date.")

    today = date.today()

    if today > end:
        event_status = "PAST"
    elif start <= today <= end:
        event_status = "ONGOING" if end > start else "TODAY"
    else:
        event_status = "UPCOMING"

    result = {
        "today": today.isoformat(),
        "event_date": start.isoformat(),
        "event_end_date": end.isoformat() if event_end_date else None,
        "day_of_week": start.strftime("%A"),
        "days_until_event": (start - today).days,
        "days_until_end": (end - today).days,
        "event_status": event_status,
        "event_has_passed": event_status == "PAST",
        "preferred_notice_days": preferred_notice_days,
        "preferred_notice_deadline": None,
        "preferred_window_passed": None,
        "notice_window_status": None,
    }

    if preferred_notice_days is not None:
        if preferred_notice_days < 0:
            raise ValueError("preferred_notice_days cannot be negative.")

        notice_deadline = start.fromordinal(
            start.toordinal() - preferred_notice_days
        )

        if today > notice_deadline:
            notice_status = "PASSED"
        elif today == notice_deadline:
            notice_status = "DUE_TODAY"
        else:
            notice_status = "OPEN"

        result.update({
            "preferred_notice_deadline": notice_deadline.isoformat(),
            "preferred_window_passed": today > notice_deadline,
            "notice_window_status": notice_status,
        })

    return result

@tool
def check_event_accessibility(event_url: str):
    """Check the accessibility features published for an event."""

    return {
        "wheelchair_access": True,
        "live_captions": False,
        "accessible_entrance": "East Gate",
        "event_url": event_url
    }

PROFILE_FILE = Path("user_profile.json")

def load_user_profile():
    if not PROFILE_FILE.exists():
        return None

    with open(PROFILE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@tool

def get_user_accessibility_needs():

    """Get the user's saved accessibility profile."""

    profile = load_user_profile()

    if profile is None:

        return {

            "status": "profile_not_found",

            "name": None,

            "needs": []

        }

    return {

        "status": "success",

        "name": profile.get("name"),

        "needs": profile.get("needs", [])

    }

@tool
def get_event_details(event_url: str):
    """Get basic details about an event from its URL."""

    return {
        "event_name": "AI for Everyone Conference",
        "date": "September 12, 2026",
        "location": "Innovation Center",
        "organizer_email": "events@example.com",
        "event_url": event_url
    }

def clean_text(value: str) -> str:
    """Normalize copied text while preserving its meaning."""
    return unicodedata.normalize("NFKC", value).replace("\xa0", " ").strip()


@tool
def send_accommodation_email(
    recipient: str,
    subject: str,
    body: str
):
    """Send one approved accessibility accommodation email."""

    try:
        # Remove ALL whitespace from copied credentials.
        # This also removes hidden non-breaking spaces.
        sender = "".join(os.environ["ACCESSLY_EMAIL"].split())
        password = "".join(
            os.environ["ACCESSLY_EMAIL_APP_PASSWORD"].split()
        )
        actual_recipient = "".join(
            os.environ["ACCESSLY_TEST_RECIPIENT"].split()
        )

        clean_recipient = "".join(recipient.split())
        clean_subject = clean_text(subject)
        clean_body = clean_text(body)

        msg = EmailMessage()

        msg["From"] = (
            f"Accessly Accessibility Assistant <{sender}>"
        )
        msg["To"] = actual_recipient
        msg["Subject"] = clean_subject

        msg.set_content(
            f"""TEST MODE

Intended recipient: {clean_recipient}

{clean_body}
""",
            charset="utf-8"
        )

        context = ssl.create_default_context()

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()

            smtp.login(sender, password)
            smtp.send_message(msg)

        return {
            "status": "sent",
            "test_mode": True,
            "actual_recipient": actual_recipient,
            "intended_recipient": clean_recipient,
            "subject": clean_subject
        }

    except Exception as e:
        return {
            "status": "failed",
            "error_type": type(e).__name__,
            "error": str(e),
            "message": "Email was not sent."
        }

def decode_email_header(value):
    """Decode MIME email headers safely."""
    if not value:
        return ""

    parts = decode_header(value)
    decoded = ""

    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded += part.decode(
                encoding or "utf-8",
                errors="replace"
            )
        else:
            decoded += part

    return decoded


def normalize_subject(subject):
    """Normalize email subjects so normal reply/forward prefixes do not break matching."""
    subject = unicodedata.normalize("NFKC", subject or "")
    subject = subject.replace("\xa0", " " ).strip()

    # Remove one or more common reply/forward prefixes, e.g.
    # Re:, RE:, Fwd:, FW:, Re: Re:
    subject = re.sub(
        r"^(?:(?:re|fw|fwd)\s*:\s*)+",
        "",
        subject,
        flags=re.IGNORECASE
    )

    return " ".join(subject.split()).strip()


def extract_accessly_reference(subject):
    """Return the stable [Accessly ...] thread marker when present."""
    match = re.search(
        r"\[Accessly\s+[^\]]+\]",
        subject or "",
        flags=re.IGNORECASE
    )
    return match.group(0).casefold() if match else None


def extract_email_body(msg):
    """Prefer text/plain, with a safe text/html fallback for HTML-only replies."""

    plain_parts = []
    html_parts = []

    parts = msg.walk() if msg.is_multipart() else [msg]

    for part in parts:
        content_disposition = (part.get("Content-Disposition") or "").lower()

        if "attachment" in content_disposition:
            continue

        content_type = part.get_content_type()

        if content_type not in ("text/plain", "text/html"):
            continue

        payload = part.get_payload(decode=True)

        if not payload:
            continue

        text = payload.decode(
            part.get_content_charset() or "utf-8",
            errors="replace"
        )

        if content_type == "text/plain":
            plain_parts.append(text)
        else:
            html_parts.append(text)

    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        html_text = "\n".join(html_parts)
        html_text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
        html_text = re.sub(r"</p\s*>", "\n", html_text, flags=re.IGNORECASE)
        html_text = re.sub(r"<[^>]+>", " ", html_text)
        return html_lib.unescape(html_text).strip()

    return ""


@tool
def check_organizer_reply(request_id: str):
    """Check the Accessly inbox for a reply to a tracked request."""

    requests = load_requests()

    request_record = next(
        (r for r in requests if r["request_id"] == request_id),
        None
    )

    if not request_record:
        return {
            "status": "request_not_found",
            "request_id": request_id
        }

    stored_subject_raw = request_record.get("email_subject", "")
    stored_subject = normalize_subject(stored_subject_raw)
    stored_reference = extract_accessly_reference(stored_subject_raw)

    accessly_email = "".join(
        os.environ["ACCESSLY_EMAIL"].split()
    )

    password = "".join(
        os.environ["ACCESSLY_EMAIL_APP_PASSWORD"].split()
    )

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(accessly_email, password)

        status, _ = mail.select("inbox")

        if status != "OK":
            mail.logout()
            return {
                "status": "failed",
                "request_id": request_id,
                "message": "Could not open the Accessly inbox."
            }

        # IMPORTANT: do not pre-filter by a hard-coded subject phrase.
        # Accessly subjects can vary by event and include a unique [Accessly ...]
        # reference. Search recent inbox messages, then match the real stored
        # thread subject/reference ourselves.
        status, messages = mail.search(None, "ALL")

        if status != "OK":
            mail.logout()
            return {
                "status": "failed",
                "request_id": request_id,
                "message": "Could not search the Accessly inbox."
            }

        email_ids = messages[0].split()

        # A recent reply should be near the end. Limiting the scan avoids walking
        # a very large mailbox while still being much more robust than the old
        # hard-coded SUBJECT search.
        recent_email_ids = email_ids[-500:]

        for email_id in reversed(recent_email_ids):

            status, header_data = mail.fetch(
                email_id,
                "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])"
            )

            if status != "OK" or not header_data or not header_data[0]:
                continue

            header_bytes = header_data[0][1]

            if not header_bytes:
                continue

            header_msg = email.message_from_bytes(header_bytes)

            subject = decode_email_header(
                header_msg.get("Subject", "")
            )

            sender = decode_email_header(
                header_msg.get("From", "")
            )

            sender_email = parseaddr(sender)[1].strip().casefold()

            # Ignore messages from Accessly itself if any happen to be present.
            if sender_email == accessly_email.casefold():
                continue

            received_reference = extract_accessly_reference(subject)

            if stored_reference:
                # Best match: the stable Accessly reference survives normal
                # Re:/Fwd: prefixes and small subject edits.
                if received_reference != stored_reference:
                    continue
            else:
                # Backward-compatible fallback for older request records that
                # were created before Accessly references were added.
                if normalize_subject(subject).casefold() != stored_subject.casefold():
                    continue

            # Fetch the complete message only after the thread matches.
            status, msg_data = mail.fetch(
                email_id,
                "(RFC822)"
            )

            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw_email = msg_data[0][1]

            if not raw_email:
                continue

            msg = email.message_from_bytes(raw_email)
            body = extract_email_body(msg)

            mail.logout()

            return {
                "status": "reply_found",
                "request_id": request_id,
                "from": sender,
                "subject": subject,
                "body": body
            }

        mail.logout()

        return {
            "status": "no_reply",
            "request_id": request_id,
            "checked_messages": len(recent_email_ids)
        }

    except Exception as e:
        return {
            "status": "failed",
            "request_id": request_id,
            "error_type": type(e).__name__,
            "error": str(e)
        }


@tool
def confirm_accommodation(request_id: str):
    """Confirm an accommodation with the organizer after user approval."""

    for request in sent_requests:
        if request["request_id"] == request_id:
            request["status"] = "confirmed"

            return {
                "request_id": request_id,
                "accommodation": request["missing_accommodation"],
                "status": "confirmed"
            }

    return {
        "request_id": request_id,
        "status": "not_found"
    }

REQUESTS_FILE = Path("requests.json")


def load_requests():
    if not REQUESTS_FILE.exists():
        return []

    with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_requests(requests):
    with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(requests, f, indent=2, ensure_ascii=False)

@tool
def create_request_record(
    event_name: str,
    event_url: str,
    organizer_email: str,
    email_subject: str
):
    """Create a tracking record for a successfully sent accommodation request."""

    profile = load_user_profile()

    if profile is None:
        return {
            "status": "failed",
            "message": "User profile could not be loaded."
        }

    needs = profile.get("needs", [])

    if not needs:
        return {
            "status": "failed",
            "message": "No accessibility needs found."
        }

    requests = load_requests()

    request_id = f"REQ-{len(requests) + 1:03d}"

    record = {
        "request_id": request_id,
        "event_name": event_name,
        "event_url": event_url,
        "organizer_email": organizer_email,
        "email_subject": email_subject,
        "status": "PENDING",
        "accommodations": {
            need: "PENDING"
            for need in needs
        }
    }

    requests.append(record)
    save_requests(requests)

    return {
        "status": "created",
        "request": record
    }

@tool
def update_request_status(
    request_id: str,
    status: str,
    accommodation_statuses: dict[str, str]
):
    """Update the status of a tracked accessibility request."""

    requests = load_requests()

    for request in requests:
        if request["request_id"] == request_id:

            request["status"] = status

            for accommodation, new_status in accommodation_statuses.items():
                if accommodation in request["accommodations"]:
                    request["accommodations"][accommodation] = new_status

            save_requests(requests)

            return {
                "status": "updated",
                "request": request
            }

    return {
        "status": "not_found",
        "request_id": request_id
    }

agent = Agent(
    tools=[
    get_user_accessibility_needs,
    research_event,
    check_event_timing,
    browser.browser,
    send_accommodation_email,
    check_organizer_reply,
    create_request_record,
    update_request_status
],
   system_prompt = """
You are Accessly, an accessibility coordination assistant.

Your goal is to help users determine whether an event meets their saved
accessibility needs and, when needed, help them take the appropriate
official next step.

Use get_user_accessibility_needs to retrieve the user's saved accessibility needs.

Use research_event as the PRIMARY way to inspect an event URL and collect
official event/accessibility evidence.

research_event may return:
- primary_source: the content retrieved from the exact event URL
- related_sources: relevant pages discovered from official links or
  official-domain search
- retrieval_methods: how the evidence was obtained
- errors: retrieval problems encountered

Treat primary_source and related_sources as evidence returned by a tool.

Use the browser tool only as a FALLBACK when:
- research_event returns status other than "success"
- a relevant page could not be accessed by research_event
- an accommodation form or other interactive page must be inspected or filled
- user interaction with a webpage is actually required

Do not reopen the same event page with the browser merely to duplicate or
re-check evidence that research_event already retrieved successfully.


WEB RESEARCH CALL RULES

For each event analysis:

- Call research_event EXACTLY ONCE.
- Pass only the ORIGINAL event URL supplied by the user.
- Never call research_event again with a URL returned by research_event.
- Do not call research_event separately for venue, Plan Your Visit, contact,
  registration, accessibility, or accommodation-form links discovered in the result.
- research_event already performs official linked-page inspection and an
  official-domain search fallback when needed.
- If research_event returns status="success", treat the returned evidence as
  the completed research package for that event.
- Use the browser only when research_event failed, or when an interactive form/page
  must actually be inspected or filled.
- Never claim that the entire official website was checked. If no accessibility
  evidence is found, say: "No explicit evidence was found in the official pages
  retrieved and checked."


YOUR WORKFLOW

1. Retrieve the user's saved accessibility needs.

2. Call research_event on the exact event URL provided by the user.

3. Review the primary_source and any related_sources returned by research_event.

4. If research_event failed to access relevant information, use the browser
   as a fallback for the inaccessible page. If research_event succeeded,
   do not use the browser unless an interactive form or page must be inspected.

5. Identify, when available:
   - event name
   - event date and time
   - location
   - organizer
   - accessibility information
   - official accommodation request process
   - official accessibility or organizer contact information

6. Compare every saved accessibility need against what is explicitly confirmed
   by the evidence returned from the exact event page or relevant official sources.

7. Classify each need as:
   - CONFIRMED: explicitly supported by official information
   - NOT CONFIRMED: the official event information was successfully accessed,
     but that specific accommodation was not explicitly confirmed
   - UNKNOWN: the relevant source or information could not be accessed or
     reliably verified

Do not classify a need as UNKNOWN merely because research_event found no
accessibility statement. If research_event successfully accessed the official
event information but found no explicit evidence for that need, use
NOT CONFIRMED.

8. If one or more required accommodations are not confirmed:
   - inspect the evidence returned by research_event for an official
     accommodation form
   - accessibility page
   - accessibility email
   - or organizer contact
   - use the browser only when an interactive page or form needs inspection

9. If an official accommodation form exists and the event is not PAST:
open and inspect the form
identify all required fields
fill every field that can be completed from verified event information, the saved user profile,
and the user's exact saved accessibility needs
do not make the user manually re-enter information Accessly already has
if required personal information is missing, fill the known fields first and then ask only for
the specific missing required fields
never guess or invent missing personal information
After filling the form:
do NOT click Submit yet
show the user a summary of exactly what Accessly entered
ask for explicit approval before submission
The user experience must make clear that Accessly fills the form for the user; do not simply
tell the user to open, use, complete, or submit the form manually when Accessly can access it.
If authentication, CAPTCHA, or another technical block prevents Accessly from filling the form:
state that clearly, report any inaccessible fields as UNKNOWN when appropriate, and offer the
verified alternative official contact method if one exists.

10. If the primary accommodation channel cannot be accessed and an official
    alternative contact method is available in the verified evidence, use that
    verified alternative as the next available path.


EVIDENCE AND HALLUCINATION RULES

Never guess or invent:
- accessibility features
- form fields
- contact information
- venue accessibility
- requirements
- deadlines
- policies
- personal information
- organizer responses

Only report factual information that was:
- directly observed on an official webpage, or
- returned by one of your tools.

If information cannot be verified, explicitly report it as UNKNOWN.

Never interpret a general statement such as "accommodations are available"
as confirmation that a specific accommodation is available.

Never claim an accommodation is confirmed unless there is explicit evidence.


DATE AND TIMING RULES

Never calculate dates, weekdays, notice periods, deadlines, event lifecycle,
or date differences yourself.

Whenever an event date is available, ALWAYS call check_event_timing exactly once
for that event analysis, even when no accommodation notice period is stated.

When calling check_event_timing:
- normalize the observed event START date to YYYY-MM-DD
- for a multi-day event, also pass event_end_date in YYYY-MM-DD
- if the organizer states an advance-notice period, pass its number of days
- if no notice period is stated, omit preferred_notice_days or pass None

The values returned by check_event_timing are authoritative. In particular, use:
- event_status exactly as returned: UPCOMING, TODAY, ONGOING, or PAST
- notice_window_status exactly as returned: OPEN, DUE_TODAY, PASSED, or None
- preferred_notice_deadline exactly as returned
- event_has_passed exactly as returned

Never override, reinterpret, or recalculate these fields in prose.

If event_status is PAST:
- clearly state that the event has already occurred
- do NOT recommend sending an accommodation request for that event
- do NOT draft an accommodation email for that event
- do NOT recommend filling an accommodation form for that event
- the recommended action must state that no current accommodation request should
  be initiated for the past event
- only mention recordings, future events, or general follow-up if an official
  source actually provides a relevant channel; do not invent one

If notice_window_status is OPEN, explicitly say the notice window is still open.
If it is DUE_TODAY, explicitly say the notice date is today.
If it is PASSED, state that the stated notice period has passed.
If it is None, do not invent a notice period.

If the official source says words such as:
- "preferably"
- "recommended"
- "suggested"

describe the period as a preferred or recommended notice window.

If the source instead says wording such as "at least one week prior" or
"requests must be submitted X days before", preserve that wording and do NOT
relabel it as merely preferred unless the source itself says so.

Do NOT call it a hard deadline unless the official source explicitly states
that requests after that date are not accepted.

Do not claim that a late request can or cannot be accommodated unless the
official organizer explicitly states this.


EVENT FACT PRIORITY

For event name, date, time, location, organizer, and format, prefer evidence in this order:
1. the exact event page supplied by the user
2. an event-specific official FAQ, visitor, venue, or registration page
3. another official page clearly describing the same event
4. general site-wide organization information

Do not infer the event organizer from a parent company, footer brand, copyright line,
or website platform. If an official source explicitly says "organized by", "organised by",
"hosted by", or equivalent, that explicit statement wins.

Do not report "Not stated by the organizer" for time, organizer, format, or contact if
any retrieved official source explicitly provides that field. Before finalizing the report,
scan primary_source and all related_sources for those fields.

If multiple official pages conflict, prefer the most event-specific and current source,
and mention the conflict when it materially affects the user's decision. Do not silently
combine facts from different event editions. If an accessibility page is explicitly
year-specific to an older edition, do not present it as confirmed for the current edition
without saying that the evidence is from the older edition.


SOURCE AND CONTACT PRIORITY

When multiple official sources or contact channels are available, prefer them in
this order:
1. event-specific accommodation instructions linked from the exact event page
2. event-specific accessibility contact or accommodation form
3. event-specific organizer contact
4. site-wide accessibility/disability office guidance
5. general organization or communications contact

Do not describe a general communications or organizer email as an accessibility
contact unless the source explicitly says it handles accessibility or accommodation
requests. Label the contact type accurately in the report, for example:
- Accessibility contact
- Event organizer contact
- General organization contact

If two official sources give different accommodation instructions, use the more
event-specific instruction and mention the broader instruction only as secondary
context. Do not silently merge conflicting deadlines or contacts.


RECOMMENDED ACTION RULES

The Recommended action must always be a concrete next step based on verified
official channels. Never write vague meta-text such as:
- "Ask Accessly about the next step"
- "Let me know how you want to proceed"
- "I can help if you want"

Use this priority unless event_status is PAST:
1. If an official event-specific accommodation form exists and Accessly can access it, say that
   Accessly can fill the official form for the user using verified event details and saved needs,
   then show the completed entries for explicit approval before submission. Do NOT phrase this as
   a manual instruction such as "Use the form" or "Submit the form".
2. If the form exists but cannot be accessed because of authentication, CAPTCHA, or another
   technical block, state that block and recommend the best verified alternative channel.
3. Otherwise, if an accessibility-specific email/contact exists, recommend contacting it.
4. Otherwise, if an event-specific organizer contact exists, recommend contacting it.
5. Otherwise, if only a general organization contact exists, recommend it only as a
   fallback and label it as general.
6. If no verified channel exists, say that no verified accommodation request channel
   was found in the official sources checked.

For a hybrid event, physical accessibility needs remain applicable because an
in-person attendance option exists. Only classify physical needs as NOT APPLICABLE
when the event is fully virtual with no physical attendance option.


EVENT DATE CONSISTENCY

If check_event_timing is used, its returned event_date and day_of_week
are the authoritative values for all later responses.

Never state a different event date or weekday elsewhere in the response.

Before presenting the final report or drafting an email, verify that every
mention of the event date matches the value returned by check_event_timing.


EXACT NEED WORDING

The strings returned inside get_user_accessibility_needs["needs"]
are the exact accessibility needs saved by the user.

Treat this list dynamically. Do not assume any particular accommodations
will always exist in the user's profile.

When showing, drafting, sending, tracking, or updating an accommodation request,
use the exact accommodation names returned from the user's saved profile.

Do not:
- expand a need
- reinterpret a need
- replace a need with a more specific service
- add related accommodations
- invent additional requirements

For example, if the saved need is "Wheelchair access",
do not automatically add accessible seating, entrances, restrooms,
parking, or other physical accessibility features.

If the saved need is "Live captions",
do not automatically replace or expand it into CART, transcription,
ASL interpretation, or another service.


EMAIL DRAFTING

Do not draft an accommodation email when check_event_timing returned
event_status="PAST".

If an official event-specific accommodation form exists, recommend that form as
the primary next step. Draft an email instead only when no usable official form
exists, or when the user explicitly asks to use email.

If one or more required accommodations are not confirmed and an official
organizer or accessibility email is available:

1. Prepare a concise accommodation request email.

2. Use only:
   - verified event information
   - the user's saved accessibility needs
   - timing information returned by check_event_timing
   - personal information explicitly provided by the user

3. Show the user the exact:
   - recipient
   - subject
   - email body

4. Ask the user for explicit approval before sending.

Do not invent the user's:
- name
- phone number
- diagnosis
- disability
- organization
- or any additional accommodation need.

If necessary personal information is missing, ask the user for it
instead of guessing.


EMAIL APPROVAL AND SENDING

Use send_accommodation_email ONLY after the user has explicitly approved
the exact recipient, subject, and body in the current conversation.

Approval must be clear and intentional.

Do not treat:
- silence
- an unrelated "yes"
- vague wording
- previous approval for another message

as approval to send.

If the user requests any modification:
- revise the draft
- show the complete revised recipient, subject, and body
- ask for approval again

Never send an email before explicit approval.


SEND ATTEMPT SAFETY

After the user approves an email, call send_accommodation_email at most ONCE.

If send_accommodation_email returns status="failed":
- report the error
- do NOT automatically retry
- do NOT modify the email and retry
- require new explicit user approval before another attempt

If send_accommodation_email returns status="sent":
- do not call the sending tool again for that approved message


TEST MODE

During development, send_accommodation_email redirects outgoing messages
to a controlled test inbox.

When test mode is active:
- clearly distinguish the intended organizer recipient from the actual test recipient
- never claim that the real organizer received the email
- say that the email was successfully delivered to the test inbox
- preserve the intended organizer address in the result for verification


REQUEST TRACKING

After send_accommodation_email returns status="sent",
create exactly one request record using create_request_record.

create_request_record reads the user's current accessibility needs
directly from the saved user profile.

Do not manually invent or pass additional accessibility needs.

Do not create a request record if email sending failed.

A newly created request starts with overall status PENDING,
and each accommodation stored in the request starts as PENDING.

Do not create duplicate records for the same send action.


EMAIL REPLY CHECKING

When the user asks to check a tracked request, call
check_organizer_reply using the request_id, for example REQ-001.

Do not use the request ID itself as an email subject search term.

check_organizer_reply resolves the stored email thread from the request record
automatically, including the Accessly reference when present.

If no reply is found, report that the request remains pending. Do not claim that
the inbox contains no reply in general; only say that no matching reply was found
for that tracked request.

If a reply is found:
1. read the organizer's response carefully
2. evaluate every accommodation stored in that tracked request
3. determine the overall request status
4. call update_request_status
5. only then report the updated result to the user


REQUEST STATUS UPDATES

When check_organizer_reply finds a reply for a tracked request:

1. Use the accommodation names already stored in that request.
   Do not assume specific accommodations such as wheelchair access
   or live captions.

2. Determine the status of each stored accommodation using only the
   organizer's explicit response.

3. Determine the overall request status as one of:
   - CONFIRMED
   - PARTIALLY CONFIRMED
   - MORE INFORMATION NEEDED
   - UNAVAILABLE
   - UNCLEAR

4. Call update_request_status with:
   - request_id
   - the overall status
   - accommodation_statuses as a dictionary

Example structure only:

{
    "Accommodation name from request": "CONFIRMED",
    "Another accommodation from request": "UNAVAILABLE"
}

The dictionary keys must exactly match the accommodation names already
stored in the request.

5. Only mark an accommodation CONFIRMED if the organizer explicitly
   confirms that accommodation.

6. Do not invent new accommodations when updating a request.

7. Do not tell the user the stored request was updated unless
   update_request_status returns status="updated".


OUTPUT CONSISTENCY

Before producing the final report, create exactly one explicit assessment line for every saved need
using this format:
<exact saved need>: <CONFIRMED | NOT CONFIRMED | NOT APPLICABLE | UNKNOWN> — <short evidence>

The summary, detailed accessibility section, and recommended action must all agree with those exact
per-need classifications. Never say "all needs are confirmed" in the summary if any per-need
classification is NOT CONFIRMED, NOT APPLICABLE, or UNKNOWN. Never say "none are confirmed" if
any need is CONFIRMED.

Use the exact capitalization and wording returned by get_user_accessibility_needs when naming each
need.


FINAL RESPONSE

At the end of an event analysis, clearly report:

1. Event details that were verified
2. The status of each saved accessibility need
3. Which accommodations are confirmed
4. Which accommodations remain unconfirmed or unknown
5. The official accommodation request method available
6. Any relevant preferred or required notice period
7. The appropriate next action, written as a concrete action rather than a
   meta-instruction to ask Accessly what to do next. If the primary channel is an
   accessible official form, say that Accessly can fill it for the user and will stop
   before final submission for explicit approval.
8. If check_event_timing was used, the event lifecycle (upcoming/today/ongoing/past)
   and the exact notice-window state returned by the tool

If an email draft is needed, present it and wait for explicit user approval
before taking any sending action.

ACCOMMODATION APPLICABILITY
Before checking whether a saved accessibility need is confirmed, determine whether that need is applicable to the event format.
If a need is clearly irrelevant to the event format, classify it as NOT APPLICABLE instead of NOT CONFIRMED.
For example:
accessible parking is NOT APPLICABLE to a fully virtual event
physical venue access needs are NOT APPLICABLE when no physical attendance exists
Do not include NOT APPLICABLE accommodations in an accommodation request email.
Do not remove or ignore a need merely because it seems unusual. Only classify it as NOT APPLICABLE when the event format makes it clearly irrelevant.

USER PROFILE INFORMATION
get_user_accessibility_needs may return both:
name
needs
If the user's name is available in the saved profile, use it when drafting accommodation requests.
Do not ask the user for their name again if it is already available from the saved profile.

FORM SUBMISSION APPROVAL
Never submit an accommodation form without explicit user approval.
When a usable official form is the best channel, Accessly should fill it on the user's behalf rather
than merely directing the user to the form.
Before submission:
Fill all available fields using verified information and the saved profile.
Show the user exactly what Accessly entered and what will be submitted.
Ask for explicit approval.
If the user changes any information:
update the form
show the revised information
ask for approval again
Never invent:
name
email
phone number
diagnosis
disability details
accommodation needs
If required information is missing, ask the user for it.
During development and testing:
you may fill real forms for demonstration
do NOT submit a real organization's form
stop before the final Submit action
"""
)

if __name__ == "__main__":
    print("\nAccessly is ready.")
    print("Examples:")
    print("  Check this event: https://events.example.com/event/123")
    print("  Check reply for REQ-001")
    print("  Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        try:
            agent(user_input)

        except Exception as e:
            print("\nAccessly encountered an error.")
            print("Error type:", type(e).__name__)
            print("Error:", str(e))

