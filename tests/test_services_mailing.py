from email.message import EmailMessage
from unittest.mock import MagicMock, call, patch

import pytest

from app.config import settings
from app.services import mailing


def test_send_email_logs_to_console_when_smtp_is_not_configured(caplog, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    caplog.set_level("INFO", logger="habitar.email")

    mailing.send_email("alumno@example.com", "Alta de usuario", "Hola Alumno")

    assert "EMAIL (console backend) -> alumno@example.com" in caplog.text
    assert "Alta de usuario" in caplog.text
    assert "Hola Alumno" in caplog.text


@pytest.mark.parametrize("smtp_user", ["", "smtp-user"])
def test_send_email_sends_message_over_tls(smtp_user, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 2525)
    monkeypatch.setattr(settings, "SMTP_FROM", "Habitar <no-reply@example.com>")
    monkeypatch.setattr(settings, "SMTP_USER", smtp_user)
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "smtp-password")
    smtp_server = MagicMock()
    smtp_server.__enter__.return_value = smtp_server

    with patch.object(mailing.smtplib, "SMTP", return_value=smtp_server) as smtp:
        mailing.send_email("alumno@example.com", "Alta de usuario", "Hola Alumno")

    smtp.assert_called_once_with("smtp.example.com", 2525, timeout=15)
    smtp_server.starttls.assert_called_once_with()
    if smtp_user:
        smtp_server.login.assert_called_once_with(smtp_user, "smtp-password")
    else:
        smtp_server.login.assert_not_called()

    sent_message = smtp_server.send_message.call_args.args[0]
    assert isinstance(sent_message, EmailMessage)
    assert sent_message["From"] == "Habitar <no-reply@example.com>"
    assert sent_message["To"] == "alumno@example.com"
    assert sent_message["Subject"] == "Alta de usuario"
    assert sent_message.get_content().strip() == "Hola Alumno"


def test_send_email_logs_smtp_failure_without_raising(caplog, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")

    with patch.object(mailing.smtplib, "SMTP", side_effect=OSError("connection refused")):
        mailing.send_email("alumno@example.com", "Alta", "Hola")

    assert "Failed to send email to alumno@example.com" in caplog.text
    assert "connection refused" in caplog.text


def test_enviar_mails_verificacion_sends_one_email_per_account(monkeypatch):
    send_email = MagicMock()
    monkeypatch.setattr(mailing, "send_email", send_email)
    contenido = [
        {
            "email": "ana@example.com",
            "nombre": "Ana",
            "apellido": "Pérez",
            "password_temporal": "123456",
        },
        {
            "email": "juan@example.com",
            "nombre": "Juan",
            "apellido": "Gómez",
            "password_temporal": "654321",
        },
    ]

    mailing.enviar_mails_verificacion(contenido)

    assert send_email.call_args_list == [
        call(
            to="ana@example.com",
            subject="HABITAR DIGITAL - Alta de usuario",
            body=(
                "Hola Ana Pérez,\ningresá a habitardigital.com con tu dirección "
                "de correo ana@example.com y contraseña 123456"
            ),
        ),
        call(
            to="juan@example.com",
            subject="HABITAR DIGITAL - Alta de usuario",
            body=(
                "Hola Juan Gómez,\ningresá a habitardigital.com con tu dirección "
                "de correo juan@example.com y contraseña 654321"
            ),
        ),
    ]
