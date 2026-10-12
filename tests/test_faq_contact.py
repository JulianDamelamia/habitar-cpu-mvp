from urllib.parse import unquote_plus

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Faq, Mensaje
from app.security import hash_password


def _client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, follow_redirects=False)


def _login(client, user):
    user.pw_hash = hash_password("password123")
    user.debe_cambiar_pw = False
    return client.post(
        "/login",
        data={"email": user.email, "password": "password123"},
    )


def test_faq_search_and_tags_render_for_students(db_session, user_factory, carrera_factory):
    carrera = carrera_factory()
    student = user_factory(email="faq-student@example.com")
    student.carrera_id = carrera.id
    db_session.add(Faq(pregunta="¿Cómo inscribirme?", respuesta="Desde actividades.", tags="inscripción, cupo"))
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.get("/faq")
        assert response.status_code == 200
        assert "faq-search" in response.text
        assert "inscripción" in response.text
        assert "Contactar a coordinación" in response.text
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)


def test_student_contact_is_delivered_to_each_coordinator_and_displayed(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    student = user_factory(email="faq-contact-student@example.com")
    student.carrera_id = carrera.id
    coordinators = [
        user_factory(rol="coordinacion", email="faq-coord-1@example.com"),
        user_factory(rol="coordinacion", email="faq-coord-2@example.com"),
    ]
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.post(
            "/faq/contacto",
            data={
                "busqueda": "inscripción",
                "asunto": "Consulta sobre inscripción",
                "cuerpo": "No encontré cómo anotarme.",
            },
        )
        assert response.status_code == 303
        messages = db_session.query(Mensaje).all()
        assert {message.destinatario_id for message in messages} == {
            coordinator.id for coordinator in coordinators
        }
        assert all(message.remitente_id == student.id for message in messages)
        assert all(not message.leido for message in messages)
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)

    coordinator_client = _client(db_session)
    try:
        assert _login(coordinator_client, coordinators[0]).status_code == 303
        inbox = coordinator_client.get("/admin/mensajes")
        assert inbox.status_code == 200
        assert "Consultas de estudiantes" in inbox.text
        assert "No encontré cómo anotarme." in inbox.text
        recipient_message = next(
            message for message in messages if message.destinatario_id == coordinators[0].id
        )
        marked = coordinator_client.post(
            f"/notificaciones/mensajes/{recipient_message.id}/leer"
        )
        assert marked.status_code == 200
        db_session.refresh(recipient_message)
        assert recipient_message.leido is True
    finally:
        coordinator_client.close()
        app.dependency_overrides.pop(get_db, None)


def test_coordinator_can_update_faq_tags(db_session, user_factory):
    coordinator = user_factory(rol="coordinacion")
    faq = Faq(pregunta="Pregunta", respuesta="Respuesta", tags="")
    db_session.add(faq)
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, coordinator).status_code == 303
        page = client.get("/admin/faq")
        assert page.status_code == 200
        assert "Etiquetas separadas por comas" in page.text
        response = client.post(
            f"/admin/faq/{faq.id}/update",
            data={
                "pregunta": "Pregunta actualizada",
                "respuesta": "Respuesta actualizada",
                "orden": "2",
                "tags": "becas, cursada, becas",
            },
        )
        assert response.status_code == 303
        db_session.refresh(faq)
        assert faq.tags == "becas, cursada"
        assert faq.tags_list == ["becas", "cursada"]
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)


def test_faq_contact_requires_search_and_coordinator_recipient(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    student = user_factory(email="faq-no-coord@example.com")
    student.carrera_id = carrera.id
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.post(
            "/faq/contacto",
            data={"busqueda": " ", "asunto": "Consulta", "cuerpo": "Necesito ayuda."},
        )
        assert response.status_code == 303
        response = client.post(
            "/faq/contacto",
            data={
                "busqueda": "inscripción",
                "asunto": "Consulta",
                "cuerpo": "Necesito ayuda.",
            },
        )
        assert response.status_code == 303
        assert "No hay cuentas de coordinación" in unquote_plus(response.headers["location"])
        assert db_session.query(Mensaje).count() == 0
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
