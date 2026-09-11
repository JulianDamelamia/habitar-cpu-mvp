from app.models import AppConfig, Asistencia
from app.services.credits import (
    accumulated_credits,
    completed_actividades,
    progress,
    required_credits,
)


def test_required_credits_usa_configuracion_y_default(db_session):
    default_value = required_credits(db_session)
    db_session.add(AppConfig(key="required_credits", value="12"))
    db_session.commit()

    assert required_credits(db_session) == 12
    assert default_value > 0


def test_accumulated_and_completed_actividades(db_session, actividad_factory, user_factory):
    estudiante = user_factory()
    primera = actividad_factory(titulo="Primera", creditos=3)
    segunda = actividad_factory(titulo="Segunda", creditos=5)
    db_session.add_all(
        [
            Asistencia(actividad_id=primera.id, user_id=estudiante.id),
            Asistencia(actividad_id=segunda.id, user_id=estudiante.id),
        ]
    )
    db_session.commit()

    assert accumulated_credits(db_session, estudiante.id) == 8
    assert {actividad.titulo for actividad, _ in completed_actividades(db_session, estudiante.id)} == {
        "Primera",
        "Segunda",
    }


def test_progress_calcula_porcentaje_y_limita_a_cien(
    db_session, actividad_factory, user_factory
):
    estudiante = user_factory()
    db_session.add(AppConfig(key="required_credits", value="5"))
    actividad = actividad_factory(creditos=8)
    db_session.add(Asistencia(actividad_id=actividad.id, user_id=estudiante.id))
    db_session.commit()

    assert progress(db_session, estudiante.id) == {
        "accumulated": 8,
        "required": 5,
        "pct": 100,
        "complete": True,
    }


def test_progress_sin_creditos_acumulados(db_session, user_factory):
    estudiante = user_factory()
    db_session.add(AppConfig(key="required_credits", value="10"))
    db_session.commit()

    assert progress(db_session, estudiante.id) == {
        "accumulated": 0,
        "required": 10,
        "pct": 0,
        "complete": False,
    }