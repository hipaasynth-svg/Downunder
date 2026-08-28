"""
Send the nightly brief (and any approved outreach) through Zoho Mail over SMTP.

The standalone agent runs outside Claude, so it can't use a hosted mail
connector — it sends directly via Zoho's SMTP server using an app password kept
in the agent's own environment:

    ZOHO_MAIL_USER=cody@drinkminot.com
    ZOHO_MAIL_PASSWORD=<zoho app password>    # an app password, NOT the login
    # optional overrides:
    ZOHO_SMTP_HOST=smtp.zoho.com
    ZOHO_SMTP_PORT=465

The nightly workflow emails Cody his own brief. When the credentials are absent,
``mail_configured()`` is False and ``send_email`` raises a clear error rather
than silently dropping the message.

Deliberately dependency-free: stdlib ``smtplib`` + ``email``.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

DEFAULT_HOST = "smtp.zoho.com"
DEFAULT_PORT = 465


def _creds() -> tuple[str, str, str, int]:
    user = os.environ.get("ZOHO_MAIL_USER", "").strip()
    password = os.environ.get("ZOHO_MAIL_PASSWORD", "")
    host = os.environ.get("ZOHO_SMTP_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST
    try:
        port = int(os.environ.get("ZOHO_SMTP_PORT", str(DEFAULT_PORT)))
    except ValueError:
        port = DEFAULT_PORT
    return user, password, host, port


def mail_configured() -> bool:
    """True only when both a Zoho user and app password are set."""
    user, password, _, _ = _creds()
    return bool(user and password)


def build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    """Build a plain-text email. Pure; no network."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body or "")
    return msg


def send_email(to: str, subject: str, body: str) -> None:
    """Send one email via Zoho SMTP.

    Raises ``RuntimeError`` when Zoho isn't configured (so nothing is silently
    dropped) and ``ValueError`` when the recipient is missing.
    """
    user, password, host, port = _creds()
    if not (user and password):
        raise RuntimeError(
            "Zoho Mail is not configured — set ZOHO_MAIL_USER and "
            "ZOHO_MAIL_PASSWORD (an app password) to enable sending."
        )
    if not (to or "").strip():
        raise ValueError("recipient (to) is required")
    msg = build_message(user, to, subject, body)
    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
