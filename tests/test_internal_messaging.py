from fastapi.testclient import TestClient
from urllib.parse import unquote_plus

from app.database import get_db
from app.main import app
from app.models import Mensaje, Notification
from app.security import hash_password
from app.services.mensajes import is_read, unread_count


def _client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, follow_redirects=False)


def test_coordinator_can_send_broadcast_and_students_read_independently(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    coordinator = user_factory(rol="coordinacion", email="coord-messages@example.com")
    coordinator.pw_hash = hash_password("password123")
    first = user_factory(email="first-message@example.com")
    first.pw_hash = hash_password("password123")
    first.carrera_id = carrera.id
    first.debe_cambiar_pw = False
    second = user_factory(email="second-message@example.com")
    second.pw_hash = hash_password("password123")
    second.carrera_id = carrera.id
    second.debe_cambiar_pw = False
    db_session.commit()

    client = _client(db_session)
    try:
        assert client.post(
            "/login",
            data={"email": coordinator.email, "password": "password123"},
        ).status_code == 303
        sent = client.post(
            "/admin/mensajes",
            data={"asunto": "Importante", "cuerpo": "Información para todos."},
        )
        assert sent.status_code == 303
        assert "todos los estudiantes" in unquote_plus(sent.headers["location"])
        message = db_session.query(Mensaje).one()
        assert message.destinatario_id is None
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    first_client = _client(db_session)
    second_client = _client(db_session)
    try:
        assert first_client.post(
            "/login",
            data={"email": first.email, "password": "password123"},
        ).status_code == 303
        assert second_client.post(
            "/login",
            data={"email": second.email, "password": "password123"},
        ).status_code == 303
        first_page = first_client.get("/notificaciones")
        second_page = second_client.get("/notificaciones")
        assert "Importante" in first_page.text
        assert "Importante" in second_page.text
        assert unread_count(db_session, first) == 1
        assert unread_count(db_session, second) == 1

        assert first_client.post(f"/notificaciones/mensajes/{message.id}/leer").status_code == 200
        db_session.refresh(message)
        assert message.leido is False
        assert is_read(db_session, message, first.id)
        assert not is_read(db_session, message, second.id)
        assert unread_count(db_session, first) == 0
        assert unread_count(db_session, second) == 1
    finally:
        first_client.close()
        second_client.close()
        app.dependency_overrides.pop(get_db, None)


def test_direct_message_is_hidden_from_other_students_and_read_only_by_recipient(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    sender = user_factory(rol="coordinacion")
    recipient = user_factory(email="recipient@example.com")
    recipient.pw_hash = hash_password("password123")
    recipient.carrera_id = carrera.id
    recipient.debe_cambiar_pw = False
    other = user_factory(email="other@example.com")
    other.pw_hash = hash_password("password123")
    other.carrera_id = carrera.id
    other.debe_cambiar_pw = False
    message = Mensaje(
        remitente_id=sender.id,
        destinatario_id=recipient.id,
        asunto="Directo",
        cuerpo="Solo destinatario.",
    )
    db_session.add(message)
    db_session.add(Notification(user_id=recipient.id, mensaje="Aviso previo"))
    db_session.commit()

    client = _client(db_session)
    try:
        assert client.post(
            "/login",
            data={"email": other.email, "password": "password123"},
        ).status_code == 303
        inbox_response = client.get("/notificaciones")
        assert inbox_response.status_code == 200
        assert "Directo" not in inbox_response.text
        response = client.post(f"/notificaciones/mensajes/{message.id}/leer")
        assert response.status_code == 404
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    assert unread_count(db_session, recipient) == 1
    assert unread_count(db_session, other) == 0
