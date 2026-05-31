import logging
import secrets
import smtplib
import string
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Optional

from email.utils import formataddr

from admin_auth.core.config import settings
from admin_auth.services.email_templates import build_otp_email

log = logging.getLogger(__name__)

# In-memory OTP storage (for production, use Redis or database)
otp_storage: Dict[str, dict] = {}


def generate_otp() -> str:
    """Generate a cryptographically secure OTP code."""
    return "".join(secrets.choice(string.digits) for _ in range(settings.OTP_LENGTH))


def store_otp(user_id: int, otp: str) -> None:
    """Store OTP with expiration time"""
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    otp_storage[str(user_id)] = {
        "otp": otp,
        "expires_at": expires_at,
        "attempts": 0,
    }


def verify_otp(user_id: int, otp: str) -> tuple[bool, int]:
    """Verify OTP for a user. Returns (success, remaining_attempts)"""
    user_key = str(user_id)
    max_attempts = 10

    if user_key not in otp_storage:
        return (False, 0)

    stored = otp_storage[user_key]

    if datetime.utcnow() > stored["expires_at"]:
        del otp_storage[user_key]
        return (False, 0)

    if stored["attempts"] >= max_attempts:
        del otp_storage[user_key]
        return (False, 0)

    stored["attempts"] += 1
    remaining = max_attempts - stored["attempts"]

    if stored["otp"] == otp:
        del otp_storage[user_key]
        return (True, remaining)

    if remaining <= 0:
        del otp_storage[user_key]

    return (False, remaining)


def clear_otp(user_id: int) -> None:
    """Clear OTP for a user"""
    user_key = str(user_id)
    if user_key in otp_storage:
        del otp_storage[user_key]


def _mask_email_for_log(email: str) -> str:
    parts = email.split("@", 1)
    if len(parts) == 2 and parts[0]:
        return f"{parts[0][:3]}***@{parts[1]}"
    return "***"


def _smtp_configured() -> bool:
    return bool((settings.SMTP_EMAIL or "").strip() and (settings.SMTP_PASSWORD or "").strip())


def send_otp_email(email: str, otp: str, full_name: str) -> bool:
    """Gửi OTP qua SMTP. Không in mã OTP ra log hay console."""
    if not _smtp_configured():
        log.error(
            "[admin_auth] Chưa cấu hình SMTP — không gửi được OTP tới %s",
            _mask_email_for_log(email),
        )
        return False

    try:
        subject, text, html = build_otp_email(full_name, otp)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr(("Học viện KMA — Chatbot", settings.SMTP_EMAIL))
        msg["To"] = email

        part1 = MIMEText(text, "plain", "utf-8")
        part2 = MIMEText(html, "html", "utf-8")
        msg.attach(part1)
        msg.attach(part2)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_EMAIL, [email], msg.as_string())

        log.info("OTP email sent successfully to %s", _mask_email_for_log(email))
        return True

    except Exception as e:
        log.error(
            "Failed to send OTP email to %s: %s",
            _mask_email_for_log(email),
            e,
        )
        return False
