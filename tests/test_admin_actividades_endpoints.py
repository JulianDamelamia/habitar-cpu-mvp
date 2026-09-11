from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import (
    ESTADO_BORRADOR,
    ESTADO_CANCELADA,
    ESTADO_PUBLICADA,
    Actividad,
)
from app.security import hash_password


@pytest.fixture
def admin_actividades_client(db_session, user_factory, carrera_factory):
    admin = user_factory(
        rol="coordinacion",
        email="coordinacion@unsam.edu.ar",
    )
    admin.pw_hash = hash_password("habitar123")
    docente = user_factory(rol="docente", email="docente@unsam.edu.ar")
    carrera = carrera_factory()
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)
    login_response = client.post(
        "/login",
        data={"email": admin.email, "password": "habitar123"},
    )
    assert login_response.status_code == 303
    yield client, db_session, docente, carrera
    client.close()
    app.dependency_overrides.pop(get_db, None)


def actividad_form_data(docente_id, carrera_id, *, titulo="Actividad nueva"):
    return {
        "titulo": titulo,
        "descripcion": "Descripción de prueba",
        "tipo": "presencial",
        "fecha_inicio": "2030-01-10T10:00",
        "fecha_fin": "2030-01-10T12:00",
        "lugar": "Campus Miguelete",
        "docente_id": str(docente_id),
        "creditos": "3",
        "cupo_max": "20",
        "carreras_asociadas": str(carrera_id),
    }


def test_admin_activities_pages_require_coordination_role(db_session, user_factory):
    student = user_factory(email="alumno@example.com")
    student.pw_hash = hash_password("student-password")
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, follow_redirects=False)
        login_response = client.post(
            "/login",
            data={"email": student.email, "password": "student-password"},
        )
        response = client.get("/admin")
        client.close()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert login_response.status_code == 303
    assert response.status_code == 403


def test_admin_activities_crud_lifecycle(admin_actividades_client):
    client, db_session, docente, carrera = admin_actividades_client

    new_page = client.get("/admin/actividades/nueva")
    assert new_page.status_code == 200
    assert "Nueva actividad" in new_page.text

    create_response = client.post(
        "/admin/actividades",
        data=actividad_form_data(docente.id, carrera.id),
    )
    assert create_response.status_code == 303
    assert unquote(create_response.headers["location"]).startswith("/admin?msg=Actividad creada")

    actividad = db_session.query(Actividad).one()
    assert actividad.titulo == "Actividad nueva"
    assert actividad.estado == ESTADO_BORRADOR
    assert actividad.docente_id == docente.id
    assert actividad.carreras_asociadas == [carrera]

    edit_response = client.get(f"/admin/actividades/{actividad.id}/editar")
    assert edit_response.status_code == 200
    assert "Editar actividad" in edit_response.text
    assert actividad.titulo in edit_response.text

    update_data = actividad_form_data(docente.id, carrera.id, titulo="Actividad actualizada")
    update_data["creditos"] = "5"
    update_response = client.post(
        f"/admin/actividades/{actividad.id}",
        data=update_data,
    )
    assert update_response.status_code == 303
    assert unquote(update_response.headers["location"]).startswith("/admin?msg=Actividad actualizada")
    db_session.refresh(actividad)
    assert actividad.titulo == "Actividad actualizada"
    assert actividad.creditos == 5

    preview_response = client.get(f"/admin/actividades/{actividad.id}/preview")
    assert preview_response.status_code == 200
    assert "Actividad actualizada" in preview_response.text

    publish_response = client.post(f"/admin/actividades/{actividad.id}/publicar")
    assert publish_response.status_code == 303
    assert unquote(publish_response.headers["location"]).startswith("/admin?msg=Actividad publicada")
    db_session.refresh(actividad)
    assert actividad.estado == ESTADO_PUBLICADA

    cancel_response = client.post(f"/admin/actividades/{actividad.id}/cancelar")
    assert cancel_response.status_code == 303
    assert unquote(cancel_response.headers["location"]).startswith("/admin?msg=Actividad cancelada")
    db_session.refresh(actividad)
    assert actividad.estado == ESTADO_CANCELADA


def test_create_activity_with_invalid_dates_redirects_with_error(admin_actividades_client):
    client, db_session, docente, carrera = admin_actividades_client
    data = actividad_form_data(docente.id, carrera.id)
    data["fecha_fin"] = "2030-01-10T09:00"

    response = client.post("/admin/actividades", data=data)

    assert response.status_code == 303
    assert unquote(response.headers["location"]).startswith("/admin?err=Fechas inválidas")
    assert db_session.query(Actividad).count() == 0


def test_missing_activity_endpoints_redirect_with_not_found(admin_actividades_client):
    client, *_ = admin_actividades_client

    for path, method in [
        ("/admin/actividades/999/editar", client.get),
        ("/admin/actividades/999/preview", client.get),
        ("/admin/actividades/999/publicar", client.post),
        ("/admin/actividades/999/cancelar", client.post),
    ]:
        response = method(path)
        assert response.status_code == 303
        assert "Actividad no encontrada" in unquote(response.headers["location"])
