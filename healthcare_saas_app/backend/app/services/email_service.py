"""Outgoing email over SMTP (configured with SMTP_* environment variables)."""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from ..core.config import settings

logger = logging.getLogger(__name__)


def email_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def _send(to: str, subject: str, body: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns False (without raising) when SMTP isn't configured or sending
    fails, so callers like forgot-password can keep their response identical either way."""

    if not email_configured():
        logger.warning("Email not sent: SMTP is not configured (set SMTP_HOST and SMTP_FROM/SMTP_USER).")
        return False
    try:
        await asyncio.to_thread(_send, to, subject, body)
        return True
    except Exception as exc:  # never log the recipient or body - they're personal data / secrets
        # Only the exception type: SMTP errors can embed the recipient address in their message
        logger.error("Email sending failed (%s).", type(exc).__name__)
        return False
