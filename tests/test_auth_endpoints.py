import pytest
from fastapi.testclient import TestClient

from app import services
from app.database import get_db
from app.main import app
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


def test_login_with_valid_credentials_redirects_and_creates_session(auth_client):
    client, user = auth_client

    response = client.post(
        "/login",
        data={"email": user.email, "password": "habitar123"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "session" in response.cookies

    protected_response = client.get("/perfil")
    assert protected_response.status_code == 200
    assert user.email in protected_response.text


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


def test_home_error_page_links_to_login(auth_client, monkeypatch):
    client, _ = auth_client

    def fail_to_load_activities(*args, **kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        services.inscripcion,
        "my_actividades",
        fail_to_load_activities,
    )

    response = client.get("/home")

    assert response.status_code == 500
    assert 'href="/login"' in response.text
