from datetime import datetime, timezone
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
    db_session.add(Notification(user_id=first.id, mensaje="Notificación nueva"))
    db_session.add(
        Notification(user_id=first.id, mensaje="Notificación leída", leido=True)
    )
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
        assert 'id="notificaciones-no-leidas" class="ml-1 text-xs text-slate-500">1</span>' in first_page.text
        assert 'id="mensajes-no-leidos" class="ml-1 text-xs text-slate-500">1</span>' in first_page.text
        assert 'id="notificaciones-no-leidas" class="ml-1 text-xs text-slate-500">0</span>' in second_page.text
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


def test_coordinator_can_reply_from_inbox_and_student_receives_reply(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    coordinator = user_factory(rol="coordinacion", email="reply-coord@example.com")
    student = user_factory(email="reply-student@example.com")
    coordinator.pw_hash = hash_password("password123")
    student.pw_hash = hash_password("password123")
    student.carrera_id = carrera.id
    student.debe_cambiar_pw = False
    inquiry = Mensaje(
        remitente_id=student.id,
        destinatario_id=coordinator.id,
        asunto="Consulta FAQ",
        cuerpo="Necesito ayuda.",
    )
    db_session.add(inquiry)
    db_session.commit()

    coordinator_client = _client(db_session)
    try:
        assert coordinator_client.post(
            "/login",
            data={"email": coordinator.email, "password": "password123"},
        ).status_code == 303
        inbox_page = coordinator_client.get(
            "/notificaciones", params={"tab": "mensajes"}
        )
        assert inbox_page.status_code == 200
        assert 'id="panel-mensajes"' in inbox_page.text
        assert 'name="lectura"' in inbox_page.text
        assert f"/admin/mensajes/{inquiry.id}/responder" in inbox_page.text
        response = coordinator_client.post(
            f"/admin/mensajes/{inquiry.id}/responder",
            data={
                "cuerpo": "Te ayudamos con tu consulta.",
                "return_to": "notificaciones",
                "lectura": "no_leidos",
                "respuesta": "no_respondidos",
                "orden": "asc",
            },
        )
        assert response.status_code == 303
        assert response.headers["location"].startswith("/notificaciones?")
        assert "tab=mensajes" in response.headers["location"]
        db_session.refresh(inquiry)
        assert inquiry.leido is True
        reply = db_session.query(Mensaje).filter(Mensaje.reply_to_id == inquiry.id).one()
        assert reply.remitente_id == coordinator.id
        assert reply.destinatario_id == student.id
        assert reply.asunto == "Re: Consulta FAQ"
    finally:
        coordinator_client.close()
        app.dependency_overrides.pop(get_db, None)

    student_client = _client(db_session)
    try:
        assert student_client.post(
            "/login",
            data={"email": student.email, "password": "password123"},
        ).status_code == 303
        response = student_client.get("/notificaciones")
        assert response.status_code == 200
        assert "Te ayudamos con tu consulta." in response.text
        assert "filter-lectura" not in response.text
        assert "responder_mensaje" not in response.text
    finally:
        student_client.close()
        app.dependency_overrides.pop(get_db, None)


def test_coordinator_can_filter_unread_unanswered_messages_and_sort_dates(
    db_session, user_factory
):
    coordinator = user_factory(rol="coordinacion")
    coordinator.pw_hash = hash_password("password123")
    students = [
        user_factory(email=f"filter-student-{index}@example.com")
        for index in range(3)
    ]
    messages = [
        Mensaje(
            remitente_id=student.id,
            destinatario_id=coordinator.id,
            asunto=subject,
            cuerpo=f"Cuerpo {subject}",
            leido=read,
            created_at=datetime(2026, 1, day, tzinfo=timezone.utc),
        )
        for student, subject, read, day in [
            (students[0], "Pendiente antiguo", False, 1),
            (students[1], "Pendiente leído", True, 2),
            (students[2], "Respondido nuevo", False, 3),
        ]
    ]
    db_session.add_all(messages)
    db_session.flush()
    db_session.add(
        Mensaje(
            remitente_id=coordinator.id,
            destinatario_id=students[2].id,
            reply_to_id=messages[2].id,
            asunto="Re: Respondido nuevo",
            cuerpo="Respuesta enviada.",
        )
    )
    db_session.commit()

    client = _client(db_session)
    try:
        assert client.post(
            "/login",
            data={"email": coordinator.email, "password": "password123"},
        ).status_code == 303
        filtered = client.get(
            "/admin/mensajes",
            params={
                "lectura": "no_leidos",
                "respuesta": "no_respondidos",
                "orden": "asc",
            },
        )
        assert filtered.status_code == 200
        assert "Pendiente antiguo" in filtered.text
        assert "Pendiente leído" not in filtered.text
        assert "Cuerpo Respondido nuevo" not in filtered.text

        notifications_tab = client.get(
            "/notificaciones",
            params={
                "tab": "mensajes",
                "lectura": "no_leidos",
                "respuesta": "no_respondidos",
                "orden": "asc",
            },
        )
        assert notifications_tab.status_code == 200
        assert "Pendiente antiguo" in notifications_tab.text
        assert "Cuerpo Respondido nuevo" not in notifications_tab.text
        assert 'aria-selected="true"' in notifications_tab.text

        chronological = client.get(
            "/admin/mensajes",
            params={"orden": "asc"},
        )
        assert chronological.text.index("Pendiente antiguo") < chronological.text.index(
            "Pendiente leído"
        ) < chronological.text.index("Respondido nuevo")
        reverse = client.get("/admin/mensajes", params={"orden": "desc"})
        assert reverse.text.index("Respondido nuevo") < reverse.text.index(
            "Pendiente leído"
        ) < reverse.text.index("Pendiente antiguo")
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
