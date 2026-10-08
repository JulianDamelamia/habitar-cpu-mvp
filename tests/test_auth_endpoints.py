from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.main import app
import app.main as main_module
from app.config import settings
from app.models import PasswordReset
from app.security import hash_password


@pytest.fixture
def auth_client(db_session, user_factory):
    user = user_factory(email="ana@alumno.unsam.edu.ar")
    user.pw_hash = hash_password("habitar123")
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)
    yield client, user
    client.close()
    app.dependency_overrides.pop(get_db, None)


def test_login_form_responds_ok(auth_client):
    client, _ = auth_client

    response = client.get("/login")

    assert response.status_code == 200
    assert 'action="/login"' in response.text
    assert 'name="password"' in response.text
    assert 'href="/recuperar-contrasena"' in response.text


def test_password_reset_sends_code_and_changes_password(
    auth_client, db_session, monkeypatch, caplog
):
    client, user = auth_client
    sent_emails = []
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    caplog.set_level("INFO", logger="habitar.auth")
    monkeypatch.setattr(
        services.mailing,
        "send_email",
        lambda to, subject, body: sent_emails.append((to, subject, body)),
    )

    response = client.post(
        "/recuperar-contrasena",
        data={"action": "request_code", "email": user.email},
    )

    assert response.status_code == 200
    assert "recibirás un código" in response.text
    assert 'name="code"' in response.text
    assert len(sent_emails) == 1
    recipient, subject, body = sent_emails[0]
    assert recipient == user.email
    assert subject == "Restablecer contraseña - Módulo Habitar"
    code = body.split("Tu código para restablecer la contraseña es: ", 1)[1].split()[0]
    assert len(code) == 6 and code.isdigit()
    assert code in caplog.text

    response = client.post(
        "/recuperar-contrasena",
        data={
            "action": "reset_password",
            "email": user.email,
            "code": code,
            "password": "nueva-clave-segura",
            "password_confirm": "nueva-clave-segura",
        },
    )

    assert response.status_code == 303
    assert urlsplit(response.headers["location"]).path == "/login"
    assert parse_qs(urlsplit(response.headers["location"]).query)["msg"] == [
        "Contraseña restablecida. Ya podés ingresar."
    ]
    assert services.identity.authenticate(
        db_session,
        user.email,
        "nueva-clave-segura",
    )
    assert db_session.query(PasswordReset).count() == 0


def test_password_reset_unknown_email_has_same_response_without_sending_mail(
    auth_client, monkeypatch
):
    client, _ = auth_client
    sent_emails = []
    monkeypatch.setattr(
        services.mailing,
        "send_email",
        lambda *args: sent_emails.append(args),
    )

    known = client.post(
        "/recuperar-contrasena",
        data={"action": "request_code", "email": "ana@alumno.unsam.edu.ar"},
    )
    unknown = client.post(
        "/recuperar-contrasena",
        data={"action": "request_code", "email": "missing@example.com"},
    )

    message = "Si existe una cuenta de estudiante con ese email, recibirás"
    assert known.status_code == unknown.status_code == 200
    assert message in known.text
    assert message in unknown.text
    assert len(sent_emails) == 1


def test_password_reset_code_locks_after_five_invalid_attempts(
    auth_client, db_session, monkeypatch
):
    client, user = auth_client
    sent_emails = []
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(
        services.mailing,
        "send_email",
        lambda to, subject, body: sent_emails.append(body),
    )
    client.post(
        "/recuperar-contrasena",
        data={"action": "request_code", "email": user.email},
    )
    code = sent_emails[0].split(
        "Tu código para restablecer la contraseña es: ", 1
    )[1].split()[0]
    wrong_code = ("0" if code[0] != "0" else "1") + code[1:]
    for _ in range(5):
        response = client.post(
            "/recuperar-contrasena",
            data={
                "action": "reset_password",
                "email": user.email,
                "code": wrong_code,
                "password": "new-password",
                "password_confirm": "new-password",
            },
        )
        assert "inválido o venció" in response.text

    assert db_session.query(PasswordReset).count() == 0
    assert services.identity.authenticate(
        db_session, user.email, "habitar123"
    ) is not None
    assert services.identity.authenticate(
        db_session, user.email, "new-password"
    ) is None
    assert len(sent_emails) == 1


def test_login_requires_career_even_when_password_is_set(auth_client, db_session):
    client, user = auth_client
    assert user.debe_cambiar_pw is True
    user.debe_cambiar_pw = False
    db_session.commit()

    response = client.post(
        "/login",
        data={"email": user.email, "password": "habitar123"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/seleccionar-carrera"
    assert "session" in response.cookies

    onboarding_response = client.get("/seleccionar-carrera")
    assert onboarding_response.status_code == 200
    assert "Nueva contraseña" in onboarding_response.text
    assert 'href="/logout"' in onboarding_response.text
    assert onboarding_response.text.count('id="password-toggle"') == 1
    assert 'input.type = visible ? "text" : "password";' in onboarding_response.text

    protected_response = client.get("/perfil")
    assert protected_response.status_code == 303
    assert protected_response.headers["location"] == "/seleccionar-carrera"


def test_login_requires_password_change_when_career_is_set(
    auth_client, carrera_factory, db_session
):
    client, user = auth_client
    user.carrera_id = carrera_factory().id
    db_session.commit()

    response = client.post(
        "/login",
        data={"email": user.email, "password": "habitar123"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/seleccionar-carrera"


def test_root_redirects_incomplete_student_to_onboarding(
    auth_client, db_session, monkeypatch
):
    client, user = auth_client
    client.post("/login", data={"email": user.email, "password": "habitar123"})

    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        lambda: Session(bind=db_session.get_bind(), expire_on_commit=False),
    )
    response = client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/seleccionar-carrera"


def test_onboarding_validates_and_saves_password_and_career(
    auth_client, carrera_factory
):
    client, user = auth_client
    carrera = carrera_factory()
    client.post("/login", data={"email": user.email, "password": "habitar123"})

    invalid_response = client.post(
        "/seleccionar-carrera",
        data={
            "password": "short",
            "password_confirm": "short",
            "carrera_id": carrera.id,
        },
    )
    assert invalid_response.status_code == 200
    assert "al menos 8 caracteres" in invalid_response.text

    mismatch_response = client.post(
        "/seleccionar-carrera",
        data={
            "password": "NuevaClave123",
            "password_confirm": "OtraClave123",
            "carrera_id": carrera.id,
        },
    )
    assert mismatch_response.status_code == 200
    assert "no coinciden" in mismatch_response.text

    invalid_career_response = client.post(
        "/seleccionar-carrera",
        data={
            "password": "NuevaClave123",
            "password_confirm": "NuevaClave123",
            "carrera_id": 999,
        },
    )
    assert invalid_career_response.status_code == 200
    assert "carrera válida" in invalid_career_response.text

    response = client.post(
        "/seleccionar-carrera",
        data={
            "password": "NuevaClave123",
            "password_confirm": "NuevaClave123",
            "carrera_id": carrera.id,
        },
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert user.carrera_id == carrera.id
    assert user.debe_cambiar_pw is False
    from app.security import verify_password
    assert verify_password("NuevaClave123", user.pw_hash)

    protected_response = client.get("/perfil")
    assert protected_response.status_code == 200
    assert user.email in protected_response.text


def test_onboarding_form_redirects_completed_student(auth_client, carrera_factory):
    client, user = auth_client
    carrera = carrera_factory()
    user.carrera_id = carrera.id
    user.debe_cambiar_pw = False
    client.post("/login", data={"email": user.email, "password": "habitar123"})

    response = client.get("/seleccionar-carrera")

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_with_invalid_password_renders_error(auth_client):
    client, user = auth_client

    response = client.post(
        "/login",
        data={"email": user.email, "password": "incorrecta"},
    )

    assert response.status_code == 200
    assert "Email o contraseña incorrectos." in response.text
    assert "session" not in response.cookies


def test_protected_endpoint_without_login_redirects_to_login(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, follow_redirects=False)
        response = client.get("/perfil")
        client.close()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_home_error_page_links_to_login(auth_client, carrera_factory, monkeypatch):
    _, user = auth_client
    user.carrera_id = carrera_factory().id
    user.debe_cambiar_pw = False
    client = TestClient(
        app,
        follow_redirects=False,
        raise_server_exceptions=False,
    )
    login_response = client.post(
        "/login",
        data={"email": user.email, "password": "habitar123"},
    )
    assert login_response.status_code == 303

    def fail_to_load_activities(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        services.inscripcion,
        "my_actividades",
        fail_to_load_activities,
    )

    response = client.get("/home")
    client.close()

    assert response.status_code == 500
    assert 'href="/login"' in response.text
