import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.fixture
def admin_client(db_session, user_factory):
    admin = user_factory(rol="coordinacion", email="admin@example.com")
    admin.pw_hash = hash_password("admin-password")
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, follow_redirects=False)
    login = client.post(
        "/login",
        data={"email": admin.email, "password": "admin-password"},
    )
    assert login.status_code == 303
    yield client, db_session
    client.close()
    app.dependency_overrides.pop(get_db, None)


def test_admin_can_update_student_required_credits_in_half_steps(
    admin_client, user_factory
):
    client, db_session = admin_client
    student = user_factory(email="student@example.com")

    response = client.patch(
        f"/admin/usuarios/{student.id}/creditos-requeridos",
        json={"creditos_requeridos": 12.5},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": student.id,
        "email": "student@example.com",
        "nombre": student.nombre,
        "apellido": student.apellido,
        "carrera_id": None,
        "creditos_requeridos": 12.5,
    }
    assert db_session.get(User, student.id).estudiante.creditos_requeridos == 12.5

    response = client.put(
        f"/admin/usuarios/{student.id}/creditos-requeridos",
        json={"creditos_requeridos": 8},
    )

    assert response.status_code == 200
    assert response.json()["creditos_requeridos"] == 8


@pytest.mark.parametrize("value", [0, -0.5, 10.25, "not-a-number"])
def test_admin_rejects_invalid_required_credits(admin_client, user_factory, value):
    client, _ = admin_client
    student = user_factory()

    response = client.patch(
        f"/admin/usuarios/{student.id}/creditos-requeridos",
        json={"creditos_requeridos": value},
    )

    assert response.status_code == 422
    assert student.estudiante.creditos_requeridos == 10


def test_admin_cannot_edit_non_student_or_missing_user(admin_client, user_factory):
    client, _ = admin_client
    coordinator = user_factory(rol="coordinacion")

    for user_id in (coordinator.id, 99999):
        response = client.patch(
            f"/admin/usuarios/{user_id}/creditos-requeridos",
            json={"creditos_requeridos": 12.5},
        )
        assert response.status_code == 404


def test_non_admin_cannot_update_student_credits(
    admin_client, user_factory, carrera_factory
):
    admin_session, db_session = admin_client
    student = user_factory()
    student.carrera_id = carrera_factory().id
    student.debe_cambiar_pw = False
    student.pw_hash = hash_password("student-password")
    db_session.commit()

    admin_session.post("/logout")
    login = admin_session.post(
        "/login",
        data={"email": student.email, "password": "student-password"},
    )
    assert login.status_code == 303

    response = admin_session.patch(
        f"/admin/usuarios/{student.id}/creditos-requeridos",
        json={"creditos_requeridos": 12.5},
    )

    assert response.status_code == 403
    assert student.estudiante.creditos_requeridos == 10


def test_users_panel_search_and_profile_edit(
    admin_client, user_factory, carrera_factory
):
    client, db_session = admin_client
    student = user_factory(email="student@example.com")
    carrera = carrera_factory()

    response = client.get("/admin/usuarios", params={"q": "student@example.com"})
    assert response.status_code == 200
    assert student.email in response.text
    assert "Agregar usuarios" in response.text
    assert "Guardar créditos" in response.text

    response = client.post(
        f"/admin/usuarios/{student.id}/actualizar",
        data={
            "nombre": "Nuevo nombre",
            "apellido": "Nuevo apellido",
            "carrera_id": str(carrera.id),
            "q": "student@example.com",
        },
    )

    assert response.status_code == 303
    assert student.nombre == "Nuevo nombre"
    assert student.apellido == "Nuevo apellido"
    assert student.carrera_id == carrera.id
    assert "q=student%40example.com" in response.headers["location"]
    db_session.refresh(student)
    assert student.estudiante.carrera_id == carrera.id