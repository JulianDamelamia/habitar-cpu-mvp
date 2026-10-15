from urllib.parse import unquote_plus

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import Faq, FaqCategoria, Mensaje
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
    category = FaqCategoria(nombre="Inscripción")
    db_session.add(category)
    db_session.flush()
    db_session.add(Faq(
        pregunta="¿Cómo inscribirme?", respuesta="Desde actividades.",
        tags="inscripción, cupo", categoria_id=category.id,
    ))
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.get("/faq")
        assert response.status_code == 200
        assert "faq-search" in response.text
        assert "inscripción" in response.text
        assert "faq-contact-subject" in response.text
        assert "Inscripción" in response.text
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
    category = FaqCategoria(nombre="Inscripción")
    db_session.add(category)
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.post(
            "/faq/contacto",
            data={
                "busqueda": "inscripción",
                "categoria_id": str(category.id),
                "cuerpo": "No encontré cómo anotarme.",
            },
        )
        assert response.status_code == 303
        messages = db_session.query(Mensaje).all()
        assert {message.destinatario_id for message in messages} == {
            coordinator.id for coordinator in coordinators
        }
        assert all(message.remitente_id == student.id for message in messages)
        assert all(message.asunto == "Inscripción" for message in messages)
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
    category = FaqCategoria(nombre="General")
    db_session.add(category)
    db_session.flush()
    faq = Faq(pregunta="Pregunta", respuesta="Respuesta", tags="", categoria_id=category.id)
    db_session.add(faq)
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, coordinator).status_code == 303
        page = client.get("/admin/faq")
        assert page.status_code == 200
        assert "Etiquetas separadas por comas" in page.text
        assert 'name="orden"' not in page.text
        new_category = client.post("/admin/faq/categorias", data={"nombre": "Cursada"})
        assert new_category.status_code == 303
        cursada = db_session.query(FaqCategoria).filter_by(nombre="Cursada").one()
        added = client.post(
            "/admin/faq",
            data={
                "pregunta": "Nueva pregunta",
                "respuesta": "Nueva respuesta",
                "categoria_id": str(category.id),
            },
        )
        assert added.status_code == 303
        inserted = db_session.query(Faq).order_by(Faq.id).all()
        assert [item.pregunta for item in inserted] == ["Pregunta", "Nueva pregunta"]
        response = client.post(
            f"/admin/faq/{faq.id}/update",
            data={
                "pregunta": "Pregunta actualizada",
                "respuesta": "Respuesta actualizada",
                "categoria_id": str(cursada.id),
                "tags": "becas, cursada, becas",
            },
        )
        assert response.status_code == 303
        db_session.refresh(faq)
        assert faq.tags == "becas, cursada"
        assert faq.tags_list == ["becas", "cursada"]
        assert faq.categoria_id == cursada.id
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)


def test_faq_contact_requires_search_and_coordinator_recipient(
    db_session, user_factory, carrera_factory
):
    carrera = carrera_factory()
    student = user_factory(email="faq-no-coord@example.com")
    student.carrera_id = carrera.id
    category = FaqCategoria(nombre="Consultas")
    db_session.add(category)
    db_session.commit()
    client = _client(db_session)
    try:
        assert _login(client, student).status_code == 303
        response = client.post(
            "/faq/contacto",
            data={"busqueda": " ", "categoria_id": str(category.id), "cuerpo": "Necesito ayuda."},
        )
        assert response.status_code == 303
        response = client.post(
            "/faq/contacto",
            data={
                "busqueda": "inscripción",
                "categoria_id": str(category.id),
                "cuerpo": "Necesito ayuda.",
            },
        )
        assert response.status_code == 303
        assert "No hay cuentas de coordinación" in unquote_plus(response.headers["location"])
        assert db_session.query(Mensaje).count() == 0
    finally:
        client.close()
        app.dependency_overrides.pop(get_db, None)
