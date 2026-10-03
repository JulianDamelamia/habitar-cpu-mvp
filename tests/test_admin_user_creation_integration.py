from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app import services
from app.database import get_db
from app.main import app
from app.models import ROL_ESTUDIANTE, User
from app.security import hash_password, verify_password


@pytest.fixture
def admin_client(db_session, user_factory):
    admin = user_factory(
        rol="coordinacion",
        email="coordinacion@unsam.edu.ar",
    )
    admin.pw_hash = hash_password("admin-password")
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)
    login_response = client.post(
        "/login",
        data={"email": admin.email, "password": "admin-password"},
    )
    assert login_response.status_code == 303
    yield client, db_session
    client.close()
    app.dependency_overrides.pop(get_db, None)


def test_user_import_creates_account_and_sends_its_temporary_password(
    admin_client, monkeypatch
):
    client, db_session = admin_client
    sent_emails = []
    monkeypatch.setattr(
        services.mailing,
        "send_email",
        lambda to, subject, body: sent_emails.append((to, subject, body)),
    )

    response = client.post(
        "/admin/usuarios/import",
        files={
            "archivo": (
                "usuarios.csv",
                "email,nombre,apellido\nana@example.com,Ana,Pérez\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 303
    assert urlsplit(response.headers["location"]).path == "/admin/usuarios"
    assert parse_qs(urlsplit(response.headers["location"]).query)["msg"] == [
        "Creados 1 usuarios nuevos."
    ]

    student = db_session.query(User).filter_by(email="ana@example.com").one()
    assert student.rol == ROL_ESTUDIANTE
    assert student.nombre == "Ana"
    assert student.apellido == "Pérez"
    assert len(sent_emails) == 1

    to, subject, body = sent_emails[0]
    assert to == student.email
    assert subject == "HABITAR DIGITAL - Alta de usuario"
    assert "Hola Ana Pérez" in body
    assert "ana@example.com" in body
    temporary_password = body.rsplit("contraseña ", maxsplit=1)[1]
    assert len(temporary_password) == 6
    assert temporary_password.isdigit()
    assert verify_password(temporary_password, student.pw_hash)


def test_user_import_with_invalid_columns_does_not_create_accounts_or_send_email(
    admin_client, monkeypatch
):
    client, db_session = admin_client
    monkeypatch.setattr(
        services.mailing, "send_email", lambda *_args, **_kwargs: pytest.fail(
            "No debería enviarse correo si falla la validación del archivo."
        )
    )

    response = client.post(
        "/admin/usuarios/import",
        files={
            "archivo": (
                "usuarios.csv",
                "email,nombre\nana@example.com,Ana\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert db_session.query(User).filter_by(email="ana@example.com").count() == 0
