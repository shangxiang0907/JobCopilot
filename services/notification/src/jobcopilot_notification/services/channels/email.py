"""SMTP email channel. Disabled gracefully when SMTP_HOST is not configured."""

import logging
from email.mime.text import MIMEText

import aiosmtplib

from jobcopilot_notification.config import settings

log = logging.getLogger(__name__)


async def send_email(*, to_address: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        log.debug("smtp_not_configured_skipped", extra={"to": to_address})
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = to_address

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        use_tls=settings.smtp_use_tls,
    )
    log.info("email_sent", extra={"to": to_address, "subject": subject})
