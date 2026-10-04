import os
import logging
from strands import Agent, tool
from strands_tools.browser import LocalChromiumBrowser
from datetime import date, datetime
import unicodedata
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv
import db
from mailer import send_test_mode_email

load_dotenv()

sent_requests = []
browser = LocalChromiumBrowser()

@tool
def check_event_timing(event_date: str, preferred_notice_days: int):
    """
    Check the timing of an event and whether the preferred accommodation
    notice window is still open.

    Args:
        event_date: Event date in YYYY-MM-DD format.
        preferred_notice_days: Number of days of advance notice requested.
    """

    event = datetime.strptime(event_date, "%Y-%m-%d").date()
    today = date.today()

    days_until_event = (event - today).days
    notice_deadline = event.fromordinal(
        event.toordinal() - preferred_notice_days
    )

    return {
        "event_date": event.isoformat(),
        "day_of_week": event.strftime("%A"),
        "days_until_event": days_until_event,
        "preferred_notice_deadline": notice_deadline.isoformat(),
        "preferred_window_passed": today > notice_deadline
    }

@tool
def check_event_accessibility(event_url: str):
    """Check the accessibility features published for an event."""

    return {
        "wheelchair_access": True,
        "live_captions": False,
        "accessible_entrance": "East Gate",
        "event_url": event_url
    }

# Set by the server (deployment_runtime.configure_agent) for each session.
# Tools never take user_id from the agent, so the agent can't pick another user.
USER_ID = None


def current_user_id():
    return USER_ID if USER_ID is not None else db.default_user_id()


def load_user_profile():
    return db.get_user_profile(current_user_id())


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
        clean_recipient = "".join(recipient.split())
        clean_subject = clean_text(subject)
        clean_body = clean_text(body)

        actual_recipient = send_test_mode_email(
            clean_recipient,
            clean_subject,
            clean_body
        )

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
    """Normalize a subject so reply prefixes and Unicode don't break matching."""
    subject = unicodedata.normalize("NFKC", subject)
    subject = subject.replace("\xa0", " ").strip()

    lowered = subject.lower()

    # Remove common reply prefix
    if lowered.startswith("re:"):
        subject = subject[3:].strip()

    return subject


@tool
def check_organizer_reply(request_id: int):
    """Check the Accessly inbox for a reply to a tracked request."""

    request_record = db.get_request(current_user_id(), request_id)

    if not request_record:
        return {
            "status": "request_not_found",
            "request_id": request_id
        }

    stored_subject = normalize_subject(
        request_record["email_subject"]
    )

    accessly_email = "".join(
        os.environ["ACCESSLY_EMAIL"].split()
    )

    password = "".join(
        os.environ["ACCESSLY_EMAIL_APP_PASSWORD"].split()
    )

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(accessly_email, password)
        mail.select("inbox")

        # Fast ASCII-only search to avoid UnicodeEncodeError
        status, messages = mail.search(
            None,
            'SUBJECT',
            '"Accessibility Accommodation Request"'
        )

        if status != "OK":
            mail.logout()
            return {
                "status": "failed",
                "request_id": request_id,
                "message": "Could not search inbox."
            }

        email_ids = messages[0].split()

        if not email_ids:
            mail.logout()
            return {
                "status": "no_reply",
                "request_id": request_id
            }

        # Newest matching messages first
        for email_id in reversed(email_ids):

            # Fetch headers only first — much faster
            status, header_data = mail.fetch(
                email_id,
                "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])"
            )

            if status != "OK":
                continue

            header_bytes = header_data[0][1]
            header_msg = email.message_from_bytes(header_bytes)

            subject = decode_email_header(
                header_msg.get("Subject", "")
            )

            if normalize_subject(subject) != stored_subject:
                continue

            # Only now fetch the full matching email
            status, msg_data = mail.fetch(
                email_id,
                "(RFC822)"
            )

            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            sender = decode_email_header(
                msg.get("From", "")
            )

            body = ""

            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)

                        if payload:
                            body = payload.decode(
                                part.get_content_charset() or "utf-8",
                                errors="replace"
                            )
                            break
            else:
                payload = msg.get_payload(decode=True)

                if payload:
                    body = payload.decode(
                        msg.get_content_charset() or "utf-8",
                        errors="replace"
                    )

            mail.logout()

            return {
                "status": "reply_found",
                "request_id": request_id,
                "from": sender,
                "subject": subject,
                "body": body.strip()
            }

        mail.logout()

        return {
            "status": "no_reply",
            "request_id": request_id
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

    record = db.create_request(
        current_user_id(),
        event_name,
        event_url,
        organizer_email,
        email_subject
    )

    if record is None:
        return {
            "status": "failed",
            "message": "No accessibility needs found."
        }

    return {
        "status": "created",
        "request": record
    }

@tool
def update_request_status(
    request_id: int,
    status: str,
    accommodation_statuses: dict[str, str]
):
    """Update the status of a tracked accessibility request."""

    status = status.strip().upper()
    accommodation_statuses = {
        accommodation: new_status.strip().upper()
        for accommodation, new_status in accommodation_statuses.items()
    }

    invalid_accommodations = [
        value
        for value in accommodation_statuses.values()
        if value not in db.NEED_STATUSES
    ]

    if status not in db.OVERALL_STATUSES or invalid_accommodations:
        return {
            "status": "failed",
            "message": "Use only the allowed status values.",
            "allowed_overall_statuses": sorted(db.OVERALL_STATUSES),
            "allowed_accommodation_statuses": sorted(db.NEED_STATUSES)
        }

    request = db.update_request(
        current_user_id(),
        request_id,
        accommodation_statuses,
        overall_status=status
    )

    if request is not None:
        return {
            "status": "updated",
            "request": request,
            "user_notified": notify_user_of_status_changes(request_id)
        }

    return {
        "status": "not_found",
        "request_id": request_id
    }


ARABIC_STATUSES = {
    "PENDING": "قيد الانتظار",
    "CONFIRMED": "مؤكد",
    "NOT CONFIRMED": "غير مؤكد",
    "NOT APPLICABLE": "لا ينطبق",
    "UNAVAILABLE": "غير متوفر",
    "UNCLEAR": "غير واضح",
    "UNKNOWN": "غير معروف",
    "MORE INFORMATION NEEDED": "يحتاج معلومات إضافية",
}


def build_status_email(preferred_language, event_name, changes):
    """Return (subject, body) for a status update, in Arabic or English."""

    if (preferred_language or "").strip().lower().startswith("ar"):
        lines = "\n".join(
            f"- {need}: {ARABIC_STATUSES.get(status, status)}"
            for need, status in changes
        )
        return (
            f"تحديث على طلب الإتاحة: {event_name}",
            f"مرحباً،\n\n"
            f"تغيّرت حالة احتياجاتك التالية في طلب الإتاحة لفعالية \"{event_name}\":\n\n"
            f"{lines}\n\n"
            f"مع تحيات فريق Accessly"
        )

    lines = "\n".join(
        f"- {need}: {status.capitalize()}"
        for need, status in changes
    )
    return (
        f"Update on your accessibility request: {event_name}",
        f"Hello,\n\n"
        f"The status of these needs changed in your accessibility request for \"{event_name}\":\n\n"
        f"{lines}\n\n"
        f"Best regards,\nThe Accessly team"
    )


def notify_user_of_status_changes(request_id):
    """Email the user once about every need whose status changed. Not an agent tool.

    The user's email never leaves this function: errors go to the server log only,
    because SMTP error messages can contain the recipient address.
    Returns True if an email was sent.
    """

    def send(user_email, preferred_language, event_name, changes):
        subject, body = build_status_email(preferred_language, event_name, changes)
        try:
            send_test_mode_email(user_email, subject, body)
            return True
        except Exception:
            logging.exception("Status notification email failed for request %s", request_id)
            return False

    try:
        return db.notify_status_changes(request_id, send) > 0
    except Exception:
        logging.exception("Status notification failed for request %s", request_id)
        return False

agent = Agent(
    tools=[
    get_user_accessibility_needs,
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

Use the browser tool to inspect the official event webpage provided by the user.


YOUR WORKFLOW

1. Retrieve the user's saved accessibility needs.

2. Inspect the official event webpage.

3. Identify, when available:
   - event name
   - event date and time
   - location
   - organizer
   - accessibility information
   - official accommodation request process
   - official accessibility or organizer contact information

4. Compare every saved accessibility need against what is explicitly confirmed
   on the official event webpage.

5. Classify each need as:
   - CONFIRMED: explicitly supported by official information
   - NOT CONFIRMED: not explicitly stated
   - UNKNOWN: the relevant information could not be accessed or verified

6. If one or more required accommodations are not confirmed:
   - look for an official accommodation form
   - accessibility page
   - accessibility email
   - or organizer contact listed on the official event page

7. If an official accommodation form exists:
open and inspect the form
identify all required fields
use verified event information when filling event-related fields
use saved user profile information when available
use the user's exact saved accessibility needs
if required personal information is missing, ask the user for it
never guess or invent missing personal information
You MAY fill the form fields after all required information is available.
After filling the form:
do NOT click Submit yet
show the user a summary of exactly what was entered
ask for explicit approval before submission
If authentication prevents access to the form:
report the inaccessible fields as UNKNOWN
look for an official alternative contact method

8. If the primary accommodation channel cannot be accessed and an official
   alternative contact method is available on the event page, use that
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

Never calculate dates, weekdays, notice periods, deadlines, or date differences
yourself.

If the event provides an advance-notice requirement or recommendation,
use check_event_timing.

When calling check_event_timing:
- normalize the observed event date to YYYY-MM-DD
- pass the number of preferred or required notice days stated by the organizer

Use the result returned by check_event_timing for:
- event date
- day of week
- days until the event
- preferred notice date
- whether the notice window has passed

If the official source says words such as:
- "preferably"
- "recommended"
- "suggested"

describe the period as a preferred or recommended notice window.

Do NOT call it a deadline unless the official source explicitly states
that it is mandatory.

If preferred_window_passed is true, state that the request is being made
after or outside the preferred notice period.

Do not claim that a late request can or cannot be accommodated unless the
official organizer explicitly states this.


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
check_organizer_reply using the numeric request_id, for example 1.

Do not use the request ID itself as an email subject search term.

check_organizer_reply resolves the stored email subject
from the request record automatically.

If no reply is found, report that the request remains pending.

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
   organizer's explicit response. Each accommodation status must be one of:
   CONFIRMED, NOT CONFIRMED, NOT APPLICABLE, UNAVAILABLE, UNCLEAR,
   UNKNOWN, MORE INFORMATION NEEDED, PENDING

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


FINAL RESPONSE

At the end of an event analysis, clearly report:

1. Event details that were verified
2. The status of each saved accessibility need
3. Which accommodations are confirmed
4. Which accommodations remain unconfirmed or unknown
5. The official accommodation request method available
6. Any relevant preferred or required notice period
7. The appropriate next action

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
Before submission:
Fill all available fields using verified information.
Show the user exactly what will be submitted.
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
    print("  Check reply for request 1")
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



