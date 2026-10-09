from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
import app.main as main_module
from app.models import (
    Asistencia,
    ESTADO_CREDITOS_ACREDITADO,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    ESTADO_PUBLICADA,
)
from app.security import hash_password
from app.services.credits import accumulated_credits
from app.services.inscripcion import inscribir


def test_manual_attendance_stays_valid_and_survey_submission_awards_credits(
    db_session, user_factory, carrera_factory, actividad_factory, monkeypatch
):
    student = user_factory(email="student@example.com")
    student.pw_hash = hash_password("student-password")
    student.carrera_id = carrera_factory().id
    student.debe_cambiar_pw = False
    teacher = user_factory(rol="docente", email="teacher@example.com")
    teacher.pw_hash = hash_password("teacher-password")
    activity = actividad_factory(
        estado=ESTADO_PUBLICADA,
        creditos=4,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=1),
    )
    activity.docentes.append(teacher.docente)
    db_session.commit()
    inscribir(db_session, activity.id, student.id)

    def override_get_db():
        yield db_session

    monkeypatch.setattr(main_module, "_init_database", lambda: None)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, follow_redirects=False) as client:
            teacher_login = client.post(
                "/login",
                data={
                    "email": teacher.email,
                    "password": "teacher-password",
                },
            )
            assert teacher_login.status_code == 303
            attendance_response = client.post(
                f"/docente/actividades/{activity.id}/marcar/{student.id}"
            )
            assert attendance_response.status_code == 303
            message = parse_qs(
                urlsplit(attendance_response.headers["location"]).query
            )["msg"][0]
            assert "debe responder la encuesta" in message

            attendance = db_session.query(Asistencia).one()
            assert attendance.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA
            assert accumulated_credits(db_session, student.id) == 0

            client.post("/logout")
            student_login = client.post(
                "/login",
                data={
                    "email": student.email,
                    "password": "student-password",
                },
            )
            assert student_login.status_code == 303
            home_response = client.get("/home")
            assert f"Responder encuesta: {activity.titulo} (4 créditos)" in home_response.text
            assert f'href="/actividades/{activity.id}/encuesta"' in home_response.text
            survey_response = client.post(
                f"/actividades/{activity.id}/encuesta",
                data={"rating": "5", "comment": "Completada"},
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert survey_response.status_code == 303
    db_session.refresh(attendance)
    assert attendance.estado_creditos == ESTADO_CREDITOS_ACREDITADO
    assert db_session.query(Asistencia).count() == 1
    assert accumulated_credits(db_session, student.id) == activity.creditos
