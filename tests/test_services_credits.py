from app.models import Asistencia
from app.services.credits import (
    accumulated_credits,
    completed_actividades,
    progress,
    required_credits,
)


def test_required_credits_usa_valor_individual_y_penalizaciones(
    db_session, user_factory
):
    estudiante = user_factory()
    estudiante.estudiante.creditos_requeridos = 12.5
    estudiante.estudiante.creditos_penalizacion = 2.0
    db_session.commit()

    assert required_credits(db_session, estudiante.id) == 14.5


def test_creditos_estudiante_tienen_defaults_individuales(db_session, user_factory):
    estudiante = user_factory()
    db_session.refresh(estudiante.estudiante)

    assert estudiante.estudiante.creditos_acreditados == 0.0
    assert estudiante.estudiante.creditos_requeridos == 10.0
    assert estudiante.estudiante.creditos_penalizacion == 0.0


def test_accumulated_and_completed_actividades(db_session, actividad_factory, user_factory):
    estudiante = user_factory()
    estudiante.estudiante.creditos_acreditados = 8.0
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
    db_session, actividad_factory, user_factory, carrera_factory
):
    estudiante = user_factory()
    carrera = carrera_factory(creditos_requeridos=5)
    estudiante.carrera_id = carrera.id
    estudiante.estudiante.creditos_requeridos = 5.0
    estudiante.estudiante.creditos_acreditados = 8.0
    actividad = actividad_factory(creditos=8)
    db_session.add(Asistencia(actividad_id=actividad.id, user_id=estudiante.id))
    db_session.commit()

    assert progress(db_session, estudiante.id) == {
        "accumulated": 8,
        "required": 5,
        "pct": 100,
        "complete": True,
    }


def test_progress_sin_creditos_acumulados(db_session, user_factory, carrera_factory):
    estudiante = user_factory()
    carrera = carrera_factory(creditos_requeridos=10)
    estudiante.carrera_id = carrera.id
    estudiante.estudiante.creditos_requeridos = 10.0
    db_session.commit()

    assert progress(db_session, estudiante.id) == {
        "accumulated": 0,
        "required": 10,
        "pct": 0,
        "complete": False,
    }