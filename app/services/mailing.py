"""Email backend: real SMTP when configured, otherwise log to stdout (MVP-safe)."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger("habitar.email")


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    if not settings.SMTP_HOST:
        if settings.ENVIRONMENT == "development":
            logger.info("EMAIL (console backend) -> %s | %s\n%s", to, subject, body)
            return True
        logger.warning("Email not sent because SMTP_HOST is not configured.")
        return False

    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    for filename, content, content_type in attachments or []:
        maintype, subtype = content_type.split("/", 1)
        msg.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 - email must never crash a request
        logger.warning("Failed to send email to %s: %s", to, exc)
        return False

def enviar_mails_verificacion(contenido:list[dict]) -> None:
    for usuario in contenido:
        cuerpo = f'Hola {usuario['nombre']} {usuario['apellido']},\ningresá a habitardigital.com con tu dirección de correo {usuario['email']} y contraseña {usuario['password_temporal']}'
        send_email(
            to = usuario['email'],
            subject = 'HABITAR DIGITAL - Alta de usuario',
            body = cuerpo
        )
