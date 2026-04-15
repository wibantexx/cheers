"""
Async email service via SMTP (aiosmtplib).

Works with any SMTP provider:
  - Gmail:   SMTP_HOST=smtp.gmail.com   SMTP_PORT=587
             (requires an App Password — google.com/apppasswords)
  - Outlook: SMTP_HOST=smtp.office365.com  SMTP_PORT=587
  - Custom:  any host:port with STARTTLS

Set SMTP_USER / SMTP_PASSWORD / SMTP_FROM in .env to enable.
When those are empty the service falls back to console logging so the app
still starts in development without email credentials.
"""

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_configured() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


async def _send(to: str, subject: str, html: str, plain: str) -> None:
    """Build and dispatch a MIME email over STARTTLS SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )


async def send_verification_email(email: str, raw_token: str) -> None:
    url = f"{settings.FRONTEND_URL}/verify-email?token={raw_token}"
    subject = "Подтвердите аккаунт Cheers"

    plain = (
        f"Привет!\n\n"
        f"Подтвердите email, перейдя по ссылке (действительна 24 часа):\n{url}\n\n"
        f"Если вы не регистрировались — просто проигнорируйте это письмо."
    )

    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#e8445a">Добро пожаловать в Cheers 🥂</h2>
      <p>Подтвердите email, чтобы начать пользоваться приложением.</p>
      <a href="{url}"
         style="display:inline-block;padding:12px 24px;background:#e8445a;
                color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Подтвердить email
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Ссылка действительна 24 часа.<br>
        Если вы не регистрировались — проигнорируйте это письмо.
      </p>
    </div>
    """

    if _is_configured():
        await _send(email, subject, html, plain)
        logger.info("Verification email sent to %s", email)
    else:
        logger.info("[DEV — no SMTP] Verification URL for %s → %s", email, url)


async def send_password_reset_email(email: str, raw_token: str) -> None:
    url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    subject = "Сброс пароля Cheers"

    plain = (
        f"Кто-то запросил сброс пароля для вашего аккаунта.\n\n"
        f"Перейдите по ссылке (действительна 1 час):\n{url}\n\n"
        f"Если это были не вы — проигнорируйте письмо. Пароль не изменится."
    )

    html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2 style="color:#e8445a">Сброс пароля</h2>
      <p>Кто-то запросил сброс пароля для вашего аккаунта Cheers.</p>
      <a href="{url}"
         style="display:inline-block;padding:12px 24px;background:#e8445a;
                color:#fff;text-decoration:none;border-radius:8px;font-weight:bold">
        Сбросить пароль
      </a>
      <p style="color:#888;font-size:12px;margin-top:24px">
        Ссылка действительна 1 час.<br>
        Если вы не запрашивали сброс — просто проигнорируйте это письмо.
      </p>
    </div>
    """

    if _is_configured():
        await _send(email, subject, html, plain)
        logger.info("Password reset email sent to %s", email)
    else:
        logger.info("[DEV — no SMTP] Reset URL for %s → %s", email, url)
