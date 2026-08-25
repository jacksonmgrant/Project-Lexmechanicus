from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from ..config import settings


class EmailDeliveryError(RuntimeError):
    pass


def _send_plain_email_sync(*, recipients: list[str], subject: str, body: str) -> None:
    if not recipients:
        raise EmailDeliveryError("No admin takedown email recipients are configured.")
    if not settings.SMTP_HOST:
        raise EmailDeliveryError("SMTP_HOST is not configured.")
    if not settings.SMTP_FROM_EMAIL:
        raise EmailDeliveryError("SMTP_FROM_EMAIL is not configured.")
    if settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
        raise EmailDeliveryError("Choose either SMTP_USE_SSL or SMTP_USE_TLS, not both.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    server_factory = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
    with server_factory(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)


async def send_plain_email(*, recipients: list[str], subject: str, body: str) -> None:
    await asyncio.to_thread(
        _send_plain_email_sync,
        recipients=recipients,
        subject=subject,
        body=body,
    )
