"""PostgreSQL storage for Accessly. Every query is scoped to one user_id."""
import hmac
import os

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

# Must match the CHECK constraints in schema.sql.
OVERALL_STATUSES = {
    "PENDING",
    "CONFIRMED",
    "PARTIALLY CONFIRMED",
    "MORE INFORMATION NEEDED",
    "UNAVAILABLE",
    "UNCLEAR",
}

NEED_STATUSES = {
    "PENDING",
    "CONFIRMED",
    "NOT CONFIRMED",
    "NOT APPLICABLE",
    "UNAVAILABLE",
    "UNCLEAR",
    "UNKNOWN",
    "MORE INFORMATION NEEDED",
}


def get_connection():
    url = os.getenv("DATABASE_URL")

    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to .env.")

    return psycopg.connect(url, row_factory=dict_row)


OTP_MAX_ATTEMPTS = 5


def default_user_id():
    """The user for running main.py from the terminal. The API uses the JWT instead."""
    value = os.getenv("DEFAULT_USER_ID")

    if not value:
        raise RuntimeError("DEFAULT_USER_ID is not set. Add it to .env.")

    return int(value)


def create_user(name, email, preferred_language):
    """Create a consenting user. Returns the new user_id, or None if the email is taken."""
    try:
        with get_connection() as conn:
            return conn.execute(
                """
                INSERT INTO users
                    (user_name, user_email, preferred_language, privacy_consent, consent_date)
                VALUES (%s, %s, %s, TRUE, now())
                RETURNING user_id
                """,
                (name, email, preferred_language)
            ).fetchone()["user_id"]
    except psycopg.errors.UniqueViolation:
        return None


def store_otp(email, code_hash):
    """Save a new login code for this email.

    Returns the user's preferred_language, or None if the email isn't registered
    or a code was already sent in the last 60 seconds.
    """
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE users
            SET otp_code = %s, otp_created_at = now(), otp_attempts = 0
            WHERE user_email = %s
              AND (otp_created_at IS NULL OR otp_created_at < now() - interval '60 seconds')
            RETURNING preferred_language
            """,
            (code_hash, email)
        ).fetchone()

    return row["preferred_language"] if row else None


def verify_otp(email, code_hash):
    """Check a login code. Returns the user_id if it's right, otherwise None.

    A code works once, for 5 minutes, and is deleted after 5 wrong attempts.
    The row is locked so parallel guesses can't get past the attempt limit.
    """
    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT user_id, otp_code, otp_attempts,
                   otp_created_at > now() - interval '5 minutes' AS fresh
            FROM users
            WHERE user_email = %s
            FOR UPDATE
            """,
            (email,)
        ).fetchone()

        if user is None or user["otp_code"] is None:
            return None

        clear = """
            UPDATE users
            SET otp_code = NULL, otp_created_at = NULL, otp_attempts = 0
            WHERE user_id = %s
        """

        if not user["fresh"] or user["otp_attempts"] >= OTP_MAX_ATTEMPTS:
            conn.execute(clear, (user["user_id"],))
            return None

        if hmac.compare_digest(user["otp_code"], code_hash):
            conn.execute(clear, (user["user_id"],))
            return user["user_id"]

        if user["otp_attempts"] + 1 >= OTP_MAX_ATTEMPTS:
            conn.execute(clear, (user["user_id"],))
        else:
            conn.execute(
                "UPDATE users SET otp_attempts = otp_attempts + 1 WHERE user_id = %s",
                (user["user_id"],)
            )

    return None


def get_user_profile(user_id):
    """Return {"name", "preferred_language", "needs"} for the user, or None if the user doesn't exist.

    The user's email is deliberately never selected here, so it can't reach the agent.
    """
    with get_connection() as conn:
        user = conn.execute(
            "SELECT user_name, preferred_language FROM users WHERE user_id = %s",
            (user_id,)
        ).fetchone()

        if user is None:
            return None

        needs = conn.execute(
            "SELECT need_name FROM needs WHERE user_id = %s AND is_active ORDER BY need_id",
            (user_id,)
        ).fetchall()

    return {
        "name": user["user_name"],
        "preferred_language": user["preferred_language"],
        "needs": [row["need_name"] for row in needs]
    }


def set_preferred_language(user_id, preferred_language):
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET preferred_language = %s WHERE user_id = %s",
            (preferred_language, user_id)
        )


def delete_user(user_id):
    """Delete the user and, through ON DELETE CASCADE, all their needs and requests.

    Returns True if a user was deleted.
    """
    with get_connection() as conn:
        return conn.execute(
            "DELETE FROM users WHERE user_id = %s",
            (user_id,)
        ).rowcount > 0


def save_user_needs(user_id, needs):
    """Replace the user's saved needs.

    Removed needs are only marked inactive, never deleted, so past requests
    keep showing them. Adding a removed need again reactivates the same row.
    """
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE needs SET is_active = FALSE
            WHERE user_id = %s AND is_active AND NOT (need_name = ANY(%s))
            """,
            (user_id, needs)
        )

        conn.cursor().executemany(
            """
            INSERT INTO needs (user_id, need_name, is_custom)
            VALUES (%s, %s, FALSE)
            ON CONFLICT (user_id, need_name) DO UPDATE SET is_active = TRUE
            """,
            [(user_id, need) for need in needs]
        )


def _fetch_requests(conn, user_id, request_id=None):
    """Load requests with their accommodations, in the shape the app already uses."""
    query = """
        SELECT r.request_id, r.event_name, r.event_url, r.organizer_email,
               r.email_subject, r.overall_status, n.need_name, rn.status
        FROM requests r
        LEFT JOIN request_needs rn ON rn.request_id = r.request_id
        LEFT JOIN needs n ON n.need_id = rn.need_id
        WHERE r.user_id = %s
    """
    params = [user_id]

    if request_id is not None:
        query += " AND r.request_id = %s"
        params.append(request_id)

    query += " ORDER BY r.request_id, n.need_id"

    records = {}

    for row in conn.execute(query, params).fetchall():
        record = records.setdefault(row["request_id"], {
            "request_id": row["request_id"],
            "event_name": row["event_name"],
            "event_url": row["event_url"],
            "organizer_email": row["organizer_email"],
            "email_subject": row["email_subject"],
            "status": row["overall_status"],
            "accommodations": {}
        })

        if row["need_name"] is not None:
            record["accommodations"][row["need_name"]] = row["status"]

    return list(records.values())


def list_requests(user_id):
    with get_connection() as conn:
        return _fetch_requests(conn, user_id)


def get_request(user_id, request_id):
    """Return one of this user's requests, or None if it isn't theirs or doesn't exist."""
    with get_connection() as conn:
        records = _fetch_requests(conn, user_id, request_id)

    return records[0] if records else None


def create_request(user_id, event_name, event_url, organizer_email, email_subject):
    """Create a request linked to all of the user's current needs. Returns None if they have no needs."""
    with get_connection() as conn:
        needs = conn.execute(
            "SELECT need_id FROM needs WHERE user_id = %s AND is_active",
            (user_id,)
        ).fetchall()

        if not needs:
            return None

        request_id = conn.execute(
            """
            INSERT INTO requests
                (user_id, event_name, event_url, organizer_email, email_subject, sent_at)
            VALUES (%s, %s, %s, %s, %s, now())
            RETURNING request_id
            """,
            (user_id, event_name, event_url, organizer_email, email_subject)
        ).fetchone()["request_id"]

        conn.cursor().executemany(
            "INSERT INTO request_needs (request_id, need_id) VALUES (%s, %s)",
            [(request_id, row["need_id"]) for row in needs]
        )

        return _fetch_requests(conn, user_id, request_id)[0]


def update_request(user_id, request_id, accommodation_statuses, overall_status=None):
    """Update a request's statuses. Returns the updated request, or None if it isn't this user's.

    Accommodation names that aren't part of the request are ignored.
    """
    with get_connection() as conn:
        owned = conn.execute(
            "SELECT 1 FROM requests WHERE request_id = %s AND user_id = %s",
            (request_id, user_id)
        ).fetchone()

        if owned is None:
            return None

        if overall_status is not None:
            conn.execute(
                "UPDATE requests SET overall_status = %s WHERE request_id = %s",
                (overall_status, request_id)
            )

        conn.cursor().executemany(
            """
            UPDATE request_needs rn
            SET status = %s
            FROM needs n
            WHERE n.need_id = rn.need_id
              AND rn.request_id = %s
              AND n.need_name = %s
            """,
            [
                (status, request_id, name)
                for name, status in accommodation_statuses.items()
            ]
        )

        return _fetch_requests(conn, user_id, request_id)[0]


def notify_status_changes(request_id, send):
    """Send one notification covering every need whose status changed since the last one.

    send(user_email, preferred_language, event_name, changes) gets changes as
    [(need_name, status), ...] and must return True only if the email went out.
    Only then are those needs marked notified, so a failed send is retried next time.
    The rows stay locked meanwhile, so two concurrent calls can't both send.
    A NULL last_notified_status counts as PENDING: a new need isn't a change.

    Returns how many needs were notified.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT rn.need_id, n.need_name, rn.status,
                   r.event_name, u.user_email, u.preferred_language
            FROM request_needs rn
            JOIN needs n ON n.need_id = rn.need_id
            JOIN requests r ON r.request_id = rn.request_id
            JOIN users u ON u.user_id = r.user_id
            WHERE rn.request_id = %s
              AND rn.status IS DISTINCT FROM COALESCE(rn.last_notified_status, 'PENDING')
            ORDER BY n.need_id
            FOR UPDATE OF rn
            """,
            (request_id,)
        ).fetchall()

        if not rows:
            return 0

        first = rows[0]
        changes = [(row["need_name"], row["status"]) for row in rows]

        if not send(first["user_email"], first["preferred_language"], first["event_name"], changes):
            return 0

        conn.cursor().executemany(
            """
            UPDATE request_needs
            SET last_notified_status = %s
            WHERE request_id = %s AND need_id = %s
            """,
            [(row["status"], request_id, row["need_id"]) for row in rows]
        )

    return len(rows)
