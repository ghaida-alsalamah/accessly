"""Email OTP login and JWT sessions. The secret comes from .env only."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

TOKEN_LIFETIME = timedelta(days=7)


def _secret():
    value = os.getenv("JWT_SECRET")

    if not value or len(value) < 32:
        raise RuntimeError("JWT_SECRET must be set in .env (at least 32 characters).")

    return value


def new_otp():
    """A random 6-digit code from a cryptographically secure source."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(code):
    """HMAC rather than a plain hash: with only a million possible codes,
    a plain SHA-256 from a leaked database could be reversed in seconds."""
    return hmac.new(_secret().encode(), b"otp:" + code.encode(), hashlib.sha256).hexdigest()


def otp_email(preferred_language, code):
    """Return (subject, body) for the login code email."""
    if (preferred_language or "").strip().lower().startswith("ar"):
        return (
            "رمز الدخول إلى Accessly",
            f"رمز الدخول الخاص بك هو: {code}\n\n"
            "الرمز صالح لمدة 5 دقائق. إذا لم تطلبه، تجاهل هذه الرسالة."
        )

    return (
        "Your Accessly login code",
        f"Your login code is: {code}\n\n"
        "It expires in 5 minutes. If you didn't request it, ignore this email."
    )


def create_token(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"user_id": user_id, "iat": now, "exp": now + TOKEN_LIFETIME},
        _secret(),
        algorithm="HS256"
    )


def user_from_header(header):
    """Return the user_id from an "Authorization: Bearer <JWT>" header, or raise 401."""
    if not header or not header.startswith("Bearer "):
        raise HTTPException(401, "Log in first: send Authorization: Bearer <token>.")

    try:
        claims = jwt.decode(
            header[7:],
            _secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "user_id"]}
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token. Log in again.")

    user_id = claims["user_id"]

    if not isinstance(user_id, int) or isinstance(user_id, bool):
        raise HTTPException(401, "Invalid or expired token. Log in again.")

    return user_id
