from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import ESTADO_PUBLICADA
from app.security import hash_password
from app.services.inscripcion import inscribir


@pytest.mark.parametrize(
    "hours_before, shows_warning",
    [(48, False), (24.1, False), (23, True)],
)
def test_activity_detail_warns_before_penalized_cancellation(
    db_session,
    user_factory,
    carrera_factory,
    actividad_factory,
    hours_before,
    shows_warning,
):
    user = user_factory(email="student@example.com")
    user.pw_hash = hash_password("password123")
    user.carrera_id = carrera_factory().id
    user.debe_cambiar_pw = False
    activity = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(hours=hours_before),
    )
    db_session.commit()
    inscribir(db_session, activity.id, user.id)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as client:
            login = client.post(
                "/login",
                data={"email": user.email, "password": "password123"},
            )
            response = client.get(f"/actividades/{activity.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert login.status_code == 303
    assert response.status_code == 200
    assert ("deberás acreditar 1 punto más por baja tardía" in response.text) is shows_warning


def test_inscription_confirmation_shows_cancellation_policy_below_banner(
    db_session, user_factory, carrera_factory, actividad_factory
):
    user = user_factory(email="student@example.com")
    user.pw_hash = hash_password("password123")
    user.carrera_id = carrera_factory().id
    user.debe_cambiar_pw = False
    activity = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.commit()

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=True) as client:
            client.post(
                "/login",
                data={"email": user.email, "password": "password123"},
            )
            response = client.post(f"/actividades/{activity.id}/inscribir")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    confirmation_position = response.text.index("¡Inscripción confirmada!")
    reminder_position = response.text.index(
        "Recordá que podés darte de baja hasta 24hs antes del inicio"
    )
    assert confirmation_position < reminder_position
    assert (
        "deberás acreditar 1 punto extra para completar el Módulo Habitar"
        in response.text
    )
