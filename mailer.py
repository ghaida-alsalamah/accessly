"""Outgoing email through the Accessly Gmail account, in TEST MODE."""
import os
import smtplib
import ssl
from email.message import EmailMessage


def send_test_mode_email(intended_recipient: str, subject: str, body: str) -> str:
    """Send through the Accessly Gmail account, redirected to ACCESSLY_TEST_RECIPIENT.

    Returns the address it was actually delivered to. Raises on failure.
    """

    # Remove ALL whitespace from copied credentials.
    # This also removes hidden non-breaking spaces.
    sender = "".join(os.environ["ACCESSLY_EMAIL"].split())
    password = "".join(
        os.environ["ACCESSLY_EMAIL_APP_PASSWORD"].split()
    )
    actual_recipient = "".join(
        os.environ["ACCESSLY_TEST_RECIPIENT"].split()
    )

    msg = EmailMessage()

    msg["From"] = (
        f"Accessly Accessibility Assistant <{sender}>"
    )
    msg["To"] = actual_recipient
    msg["Subject"] = subject

    msg.set_content(
        f"""TEST MODE

Intended recipient: {intended_recipient}

{body}
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

    return actual_recipient
