"""Public-hosting boundaries around the unchanged local agent."""

import contextvars
import hashlib
import ipaddress
import json
import os
import re
import socket
import sqlite3
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parent

load_dotenv(ROOT / ".env")


PUBLIC = os.getenv("ACCESSLY_PUBLIC_MODE", "0") == "1"

OWNER = contextvars.ContextVar(
    "accessly_visitor",
    default="local"
)

DATA_ROOT = Path(
    os.getenv(
        "ACCESSLY_DATA_DIR",
        str(ROOT)
    )
).resolve()

KOYEB_DOMAIN = os.getenv(
    "KOYEB_PUBLIC_DOMAIN",
    ""
).strip()

CONFIGURED_ORIGINS = (
    os.getenv("ACCESSLY_ALLOWED_ORIGINS")
    or os.getenv("RENDER_EXTERNAL_URL")
    or (
        "https://" + KOYEB_DOMAIN
        if KOYEB_DOMAIN
        else None
    )
)

ORIGINS = [
    origin.strip().rstrip("/")
    for origin in (
        CONFIGURED_ORIGINS
        or "http://localhost:8443,http://127.0.0.1:8443"
    ).split(",")
    if origin.strip()
]


if PUBLIC:

    if (
        not CONFIGURED_ORIGINS
        or not all(
            origin.startswith("https://")
            for origin in ORIGINS
        )
    ):
        raise RuntimeError(
            "Public mode requires explicit HTTPS "
            "ACCESSLY_ALLOWED_ORIGINS."
        )

    if not os.getenv(
        "ACCESSLY_DATA_DIR"
    ):
        raise RuntimeError(
            "Public mode requires persistent "
            "ACCESSLY_DATA_DIR."
        )

    if not os.getenv(
        "ACCESSLY_TEST_RECIPIENT"
    ):
        raise RuntimeError(
            "Public mode requires a controlled "
            "ACCESSLY_TEST_RECIPIENT."
        )

    DATA_ROOT.mkdir(
        parents=True,
        exist_ok=True
    )


def visitor_directory():

    if not PUBLIC:
        return DATA_ROOT

    directory = (
        DATA_ROOT
        / "visitors"
        / OWNER.get()
    )

    directory.mkdir(
        parents=True,
        exist_ok=True
    )

    return directory


def visitor_from_header(header):

    if (
        not header
        or not re.fullmatch(
            r"Bearer [0-9a-f]{64}",
            header
        )
    ):
        raise HTTPException(
            401,
            "A browser visitor session is required. "
            "Refresh the page."
        )

    return hashlib.sha256(
        header[7:].encode()
    ).hexdigest()


def atomic_json(path, value):

    path = Path(path)

    temporary = path.with_suffix(
        ".tmp"
    )

    temporary.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    temporary.replace(path)


def require_public_url(url):

    parsed = urlsplit(url)

    if (
        parsed.scheme not in (
            "https",
            "http"
        )
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port
        not in (
            None,
            80,
            443
        )
    ):
        raise ValueError(
            "Use a public HTTP(S) event URL "
            "on a standard web port."
        )

    addresses = socket.getaddrinfo(
        parsed.hostname,
        parsed.port or 443,
        type=socket.SOCK_STREAM
    )

    if (
        not addresses
        or any(
            not ipaddress.ip_address(
                item[4][0]
            ).is_global
            for item in addresses
        )
    ):
        raise ValueError(
            "Private, local and metadata network "
            "addresses are not available."
        )


def reserve_action():

    if not PUBLIC:
        return

    with sqlite3.connect(
        DATA_ROOT / "usage.sqlite"
    ) as database:

        database.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                owner TEXT,
                day TEXT,
                count INTEGER,
                PRIMARY KEY(owner, day)
            )
            """
        )

        database.execute(
            "BEGIN IMMEDIATE"
        )

        day = time.strftime(
            "%Y-%m-%d",
            time.gmtime()
        )

        total = database.execute(
            """
            SELECT COALESCE(
                SUM(count),
                0
            )
            FROM usage
            WHERE day=?
            """,
            (day,)
        ).fetchone()[0]

        used = database.execute(
            """
            SELECT count
            FROM usage
            WHERE owner=?
            AND day=?
            """,
            (
                OWNER.get(),
                day
            )
        ).fetchone()

        if (
            total
            >= int(
                os.getenv(
                    "ACCESSLY_DAILY_ACTION_LIMIT",
                    "60"
                )
            )
            or (
                used
                and used[0]
                >= int(
                    os.getenv(
                        "ACCESSLY_VISITOR_DAILY_LIMIT",
                        "12"
                    )
                )
            )
        ):
            raise HTTPException(
                429,
                "The demo has reached its daily "
                "usage limit. Please try again tomorrow."
            )

        database.execute(
            """
            INSERT INTO usage
            VALUES (?, ?, 1)
            ON CONFLICT(owner, day)
            DO UPDATE
            SET count=count+1
            """,
            (
                OWNER.get(),
                day
            )
        )


def configure_agent(
    namespace,
    context
):
    """
    Point existing persistence at this visitor,
    then enforce public-demo boundaries.

    The original browser tool is intentionally
    left unchanged.
    """

    directory = visitor_directory()

    globals_ = namespace[
        "load_user_profile"
    ].__globals__

    globals_[
        "PROFILE_FILE"
    ] = (
        directory
        / "user_profile.json"
    )

    globals_[
        "REQUESTS_FILE"
    ] = (
        directory
        / "requests.json"
    )

    if not PUBLIC:
        return

    from strands import tool

    agent = namespace["agent"]
    browser = namespace["browser"]

    globals_[
        "save_requests"
    ] = lambda records: atomic_json(
        directory / "requests.json",
        records
    )

    agent.callback_handler = (
        lambda **kwargs: None
    )

    marker = (
        "[Accessly "
        + context["reference"]
        + "]"
    )

    context["approval"] = None
    context["pending_record"] = None

    # Keep browser reference for cleanup in api.py.
    context["browser"] = browser

    # ---------------------------------------------------------
    # IMPORTANT
    #
    # Do NOT modify or replace browser.browser here.
    #
    # The agent keeps the exact original browser tool
    # created in main.py.
    #
    # No readonly_browser wrapper.
    # No Playwright network interception.
    # No service worker modification.
    # No tool_registry replacement for browser.
    # ---------------------------------------------------------


    # ---------------------------------------------------------
    # Email safety guard
    # ---------------------------------------------------------

    original_send = namespace[
        "send_accommodation_email"
    ]

    @tool(
        name="send_accommodation_email"
    )
    def guarded_send(
        recipient: str,
        subject: str,
        body: str
    ):
        """
        Send an exactly approved accessibility
        draft once, to the configured test inbox only.
        """

        candidate = {
            "to": recipient,
            "subject": subject,
            "body": body,
        }

        from result_presenter import plain_email

        normalize = lambda value: " ".join(
            unicodedata.normalize(
                "NFKC",
                plain_email(value)
            ).split()
        )

        approval = context.get(
            "approval"
        )

        if (
            not approval
            or marker not in subject
            or any(
                normalize(
                    candidate[key]
                )
                != normalize(
                    approval[key]
                )
                for key in candidate
            )
        ):
            return {
                "status": "failed",
                "message": (
                    "Show the exact complete draft, "
                    "including its Accessly reference "
                    "in the subject, and ask the user "
                    "to click Approve & Send."
                ),
            }

        context[
            "approval"
        ] = None

        # Cosmetic model formatting must never
        # change the exact approved outgoing email.
        recipient = approval["to"]
        subject = approval["subject"]
        body = approval["body"]

        outcome = original_send(
            recipient,
            subject,
            body
        )

        if (
            outcome.get("status")
            == "sent"
        ):
            context[
                "pending_record"
            ] = {
                "subject": subject,
                "recipient": recipient,
            }

            outcome[
                "actual_recipient"
            ] = (
                "configured test inbox"
            )

        return outcome

    agent.tool_registry.replace(
        guarded_send
    )


    # ---------------------------------------------------------
    # Request tracking guard
    # ---------------------------------------------------------

    original_record = namespace[
        "create_request_record"
    ]

    @tool(
        name="create_request_record"
    )
    def guarded_record(
        event_name: str,
        event_url: str,
        organizer_email: str,
        email_subject: str
    ):
        """
        Track this visitor's successfully sent
        test email exactly once.
        """

        pending = context.get(
            "pending_record"
        )

        if (
            not pending
            or pending["subject"]
            != email_subject
            or pending["recipient"]
            != organizer_email
        ):
            return {
                "status": "failed",
                "message": (
                    "No matching successful send "
                    "is awaiting a tracking record."
                ),
            }

        outcome = original_record(
            event_name,
            event_url,
            organizer_email,
            email_subject
        )

        if (
            outcome.get("status")
            == "created"
        ):

            # Preserve already-established
            # non-applicable needs in tracking.

            non_applicable = {
                item["name"]
                for item in (
                    context.get(
                        "result"
                    )
                    or {}
                ).get(
                    "accessibility_results",
                    []
                )
                if item["status"]
                == "NOT APPLICABLE"
            }

            record = outcome.get(
                "request",
                {}
            )

            for need in non_applicable:

                if need in record.get(
                    "accommodations",
                    {}
                ):
                    record[
                        "accommodations"
                    ][need] = (
                        "NOT APPLICABLE"
                    )

            if (
                non_applicable
                and record.get(
                    "request_id"
                )
            ):
                records = globals_[
                    "load_requests"
                ]()

                for (
                    index,
                    stored
                ) in enumerate(
                    records
                ):
                    if (
                        stored[
                            "request_id"
                        ]
                        == record[
                            "request_id"
                        ]
                    ):
                        records[
                            index
                        ] = record

                        break

                globals_[
                    "save_requests"
                ](
                    records
                )

            context[
                "pending_record"
            ] = None

        return outcome

    agent.tool_registry.replace(
        guarded_record
    )


def authorize_approval(
    message,
    context
):

    if not PUBLIC:
        return

    context[
        "approval"
    ] = None

    draft = (
        context.get(
            "result"
        )
        or {}
    ).get(
        "draft"
    )

    if not draft:
        return

    exact = (
        "I explicitly approve sending "
        "this exact email once:\n"
        f"To: {draft['to']}\n"
        f"Subject: {draft['subject']}\n"
        "Body:\n"
        f"{draft['body']}"
    )

    if (
        message
        .replace(
            "\r\n",
            "\n"
        )
        .strip()
        == exact.strip()
    ):
        context[
            "approval"
        ] = dict(
            draft
        )
