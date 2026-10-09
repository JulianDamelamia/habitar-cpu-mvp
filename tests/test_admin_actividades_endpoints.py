from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import (
    Asistencia,
    Docente,
    Estudiante,
    ESTADO_BORRADOR,
    ESTADO_CANCELADA,
    ESTADO_CREDITOS_ACREDITADO,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    ESTADO_PUBLICADA,
    Actividad,
    User,
)
from app.security import hash_password
from app.routers.admin.admin_actividades import parse_intervalo_tiempo
from app.services.parsing import parse_duracion
from app.services.credits import accumulated_credits


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
        "docentes_ids": str(docente_id),
        "docentes_nombres": ["Eva"],
        "docentes_apellidos": ["Invitada"],
        "creditos": "2.5",
        "cupo_max": "20",
        "carreras_asociadas": str(carrera_id),
    }


def redirect_query(response, name):
    return parse_qs(urlsplit(response.headers["location"]).query).get(name, [""])[0]


def testparse_duracion_accepts_hh_mm():
    assert parse_duracion("02:15") == timedelta(hours=2, minutes=15)


def testparse_duracion_rejects_invalid_format():
    with pytest.raises(ValueError, match="HH:MM"):
        parse_duracion("2:15")


def test_parse_dates_rejects_dates_before_today():
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)

    with pytest.raises(ValueError, match="anteriores al día de hoy"):
        parse_intervalo_tiempo(
            f"{yesterday.isoformat()}T10:00",
            duracion="01:00",
            modo_finalizacion="duracion",
        )


def test_admin_activities_pages_require_coordination_role(
    db_session, user_factory, carrera_factory
):
    student = user_factory(email="alumno@example.com")
    student.pw_hash = hash_password("student-password")
    student.carrera_id = carrera_factory().id
    student.debe_cambiar_pw = False
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
        response = client.get("/admin/actividades")
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
        data=actividad_form_data(docente.docente_id, carrera.id),
    )
    assert create_response.status_code == 303
    assert redirect_query(create_response, "msg").startswith("Actividad creada")

    actividad = db_session.query(Actividad).one()
    assert actividad.titulo == "Actividad nueva"
    assert actividad.estado == ESTADO_BORRADOR
    assert {d.nombre_completo for d in actividad.docentes} == {
        docente.docente.nombre_completo,
        "Eva Invitada",
    }
    assert actividad.creditos == 2.5
    assert actividad.carreras_asociadas == [carrera]

    panel_response = client.get(
        "/admin/actividades",
        params={"carreras_asociadas": str(carrera.id)},
    )
    assert panel_response.status_code == 200
    assert f"carreras_asociadas={carrera.id}&amp;sort=nombre&amp;direction=asc" in panel_response.text
    sorted_panel_response = client.get(
        "/admin/actividades",
        params={
            "carreras_asociadas": str(carrera.id),
            "sort": "fecha",
            "direction": "desc",
        },
    )
    assert sorted_panel_response.status_code == 200
    assert f"carreras_asociadas={carrera.id}&amp;sort=fecha&amp;direction=asc" in sorted_panel_response.text
    assert "text-indigo-600" in sorted_panel_response.text

    edit_response = client.get(f"/admin/actividades/{actividad.id}/editar")
    assert edit_response.status_code == 200
    assert "Editar actividad" in edit_response.text
    assert actividad.titulo in edit_response.text

    update_data = actividad_form_data(docente.docente_id, carrera.id, titulo="Actividad actualizada")
    update_data["creditos"] = "5"
    update_response = client.post(
        f"/admin/actividades/{actividad.id}",
        data=update_data,
    )
    assert update_response.status_code == 303
    assert redirect_query(update_response, "msg").startswith("Actividad actualizada")
    db_session.refresh(actividad)
    assert actividad.titulo == "Actividad actualizada"
    assert actividad.creditos == 5

    preview_response = client.get(f"/admin/actividades/{actividad.id}/preview")
    assert preview_response.status_code == 200
    assert "Actividad actualizada" in preview_response.text

    publish_response = client.post(f"/admin/actividades/{actividad.id}/publicar")
    assert publish_response.status_code == 303
    assert redirect_query(publish_response, "msg").startswith("Actividad publicada")
    db_session.refresh(actividad)
    assert actividad.estado == ESTADO_PUBLICADA

    cancel_response = client.post(f"/admin/actividades/{actividad.id}/cancelar")
    assert cancel_response.status_code == 303
    assert redirect_query(cancel_response, "msg").startswith("Actividad cancelada")
    db_session.refresh(actividad)
    assert actividad.estado == ESTADO_CANCELADA


def test_create_activity_rejects_credits_not_in_half_point_steps(admin_actividades_client):
    client, db_session, docente, carrera = admin_actividades_client
    data = actividad_form_data(docente.docente_id, carrera.id)
    data["creditos"] = "1.3"

    response = client.post("/admin/actividades", data=data)

    assert response.status_code == 303
    assert "múltiplo de 0,5" in redirect_query(response, "err")
    assert db_session.query(Actividad).count() == 0


def test_user_with_matching_name_links_to_existing_docente(
    db_session, user_factory
):
    staff = user_factory(rol="docente")
    student = User(
        email="coincide@example.com",
        pw_hash="test-hash",
        nombre=staff.nombre,
        apellido=staff.apellido,
        estudiante=Estudiante(),
    )
    db_session.add(student)
    db_session.commit()

    assert db_session.query(Docente).count() == 1
    assert student.docente_id == staff.docente_id


def test_create_activity_with_invalid_dates_redirects_with_error(admin_actividades_client):
    client, db_session, docente, carrera = admin_actividades_client
    data = actividad_form_data(docente.id, carrera.id)
    data["fecha_fin"] = "2030-01-10T09:00"

    response = client.post("/admin/actividades", data=data)

    assert response.status_code == 303
    assert redirect_query(response, "err").startswith("Fechas inválidas")
    assert db_session.query(Actividad).count() == 0


def test_activity_without_career_cannot_be_published(admin_actividades_client):
    client, db_session, docente, _ = admin_actividades_client
    data = actividad_form_data(docente.id, 0)
    data.pop("carreras_asociadas")

    create_response = client.post("/admin/actividades", data=data)

    assert create_response.status_code == 303
    actividad = db_session.query(Actividad).one()
    assert actividad.estado == ESTADO_BORRADOR
    assert actividad.carreras_asociadas == []

    publish_response = client.post(f"/admin/actividades/{actividad.id}/publicar")

    assert publish_response.status_code == 303
    assert "sin carreras asociadas" in redirect_query(publish_response, "err")
    db_session.refresh(actividad)
    assert actividad.estado == ESTADO_BORRADOR


def test_disabling_activity_survey_releases_pending_credits(
    admin_actividades_client, user_factory
):
    client, db_session, docente, carrera = admin_actividades_client
    create_response = client.post(
        "/admin/actividades",
        data=actividad_form_data(docente.id, carrera.id),
    )
    assert create_response.status_code == 303
    activity = db_session.query(Actividad).one()
    assert activity.encuesta_obligatoria is True

    student = user_factory()
    db_session.add(
        Asistencia(
            actividad_id=activity.id,
            user_id=student.id,
            estado_creditos=ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
    )
    db_session.commit()
    update_data = actividad_form_data(
        docente.id, carrera.id, titulo=activity.titulo
    )
    update_data["encuesta_obligatoria"] = "false"

    response = client.post(f"/admin/actividades/{activity.id}", data=update_data)

    assert response.status_code == 303
    db_session.refresh(activity)
    attendance = db_session.query(Asistencia).one()
    assert activity.encuesta_obligatoria is False
    assert attendance.estado_creditos == ESTADO_CREDITOS_ACREDITADO
    assert accumulated_credits(db_session, student.id) == activity.creditos


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
        assert "Actividad no encontrada" in redirect_query(response, "err")
