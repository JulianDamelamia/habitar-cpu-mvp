import pytest
from datetime import datetime, timedelta, timezone

from app.models import (
    ESTADO_PUBLICADA,
    INSCRIPCION_ALTA,
    INSCRIPCION_BAJA,
    Inscripcion,
    Notification,
)
from app.services.credits import required_credits
from app.services.inscripcion import (
    EnrollError,
    active_enrollment,
    inscribir,
    inscriptos,
    my_actividades,
    cancellation_penalty_applies,
    unenroll,
)
from app.services.consultas_comunes import is_enrolled


def test_inscribir_y_consultar_inscripcion(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()

    resultado = inscribir(db_session, actividad.id, usuario.id)

    assert resultado.id == actividad.id
    assert is_enrolled(db_session, actividad.id, usuario.id)
    assert active_enrollment(db_session, actividad.id, usuario.id).estado == INSCRIPCION_ALTA
    assert [e.user_id for e in inscriptos(db_session, actividad.id)] == [usuario.id]


@pytest.mark.parametrize(
    "actividad_id, estado, mensaje",
    [(9999, None, "no existe"), (None, "borrador", "no está disponible")],
)
def test_inscribir_rechaza_actividad_invalida(
    db_session, actividad_factory, user_factory, actividad_id, estado, mensaje
):
    usuario = user_factory()
    if estado:
        actividad_id = actividad_factory(estado=estado).id

    with pytest.raises(EnrollError, match=mensaje):
        inscribir(db_session, actividad_id, usuario.id)


def test_inscribir_rechaza_duplicado_y_cupo_lleno(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA, cupo_max=1)
    primero = user_factory()
    segundo = user_factory()
    inscribir(db_session, actividad.id, primero.id)

    with pytest.raises(EnrollError, match="Ya estás inscripto"):
        inscribir(db_session, actividad.id, primero.id)
    with pytest.raises(EnrollError, match="No quedan cupos"):
        inscribir(db_session, actividad.id, segundo.id)


def test_unenroll_permite_reinscripcion(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()
    inscribir(db_session, actividad.id, usuario.id)

    unenroll(db_session, actividad.id, usuario.id)
    assert not is_enrolled(db_session, actividad.id, usuario.id)
    assert db_session.query(Inscripcion).filter_by(actividad_id=actividad.id).one().estado != INSCRIPCION_ALTA
    inscribir(db_session, actividad.id, usuario.id)
    assert is_enrolled(db_session, actividad.id, usuario.id)


@pytest.mark.parametrize(
    "hours_before, expected_penalty",
    [(48, False), (24, False), (23, True)],
)
def test_unenroll_penaliza_solo_dentro_de_24_horas(
    db_session, actividad_factory, user_factory, hours_before, expected_penalty
):
    now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=now + timedelta(hours=hours_before),
    )
    usuario = user_factory()
    inscribir(db_session, actividad.id, usuario.id)

    penalizada = unenroll(db_session, actividad.id, usuario.id, now=now)

    db_session.refresh(usuario.estudiante)
    db_session.refresh(db_session.query(Inscripcion).one())
    assert penalizada is expected_penalty
    assert db_session.query(Inscripcion).one().estado == INSCRIPCION_BAJA
    assert usuario.estudiante.creditos_penalizacion == (1.0 if expected_penalty else 0.0)
    assert required_credits(db_session, usuario.id) == (
        11.0 if expected_penalty else 10.0
    )
    notifications = db_session.query(Notification).filter_by(user_id=usuario.id).all()
    assert len(notifications) == (1 if expected_penalty else 0)
    if expected_penalty:
        assert "baja tardía" in notifications[0].mensaje
        assert "menos de 24 horas" in notifications[0].mensaje


def test_cancellation_penalty_applies_respeta_horas_y_estado(
    actividad_factory,
):
    now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    actividad_a_24_horas = actividad_factory(
        fecha_inicio=now + timedelta(hours=24)
    )
    actividad_a_23_horas = actividad_factory(
        fecha_inicio=now + timedelta(hours=23)
    )
    actividad_iniciada = actividad_factory(
        fecha_inicio=now - timedelta(minutes=1)
    )
    actividad_finalizada = actividad_factory(
        fecha_inicio=now - timedelta(hours=2)
    )
    actividad_finalizada.fecha_fin = now - timedelta(hours=1)

    assert not cancellation_penalty_applies(actividad_a_24_horas, now=now)
    assert cancellation_penalty_applies(actividad_a_23_horas, now=now)
    assert not cancellation_penalty_applies(actividad_iniciada, now=now)
    assert not cancellation_penalty_applies(actividad_finalizada, now=now)


def test_unenroll_no_penaliza_actividad_ya_iniciada(
    db_session, actividad_factory, user_factory
):
    now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=now - timedelta(minutes=30),
    )
    usuario = user_factory()
    inscribir(db_session, actividad.id, usuario.id)

    penalizada = unenroll(db_session, actividad.id, usuario.id, now=now)

    assert penalizada is False
    assert usuario.estudiante.creditos_penalizacion == 0.0
    assert db_session.query(Notification).filter_by(user_id=usuario.id).count() == 0


def test_unenroll_sin_inscripcion_falla(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()

    with pytest.raises(EnrollError, match="No estás inscripto"):
        unenroll(db_session, actividad.id, usuario.id)


def test_my_actividades_filtra_publicadas_y_ordena(db_session, actividad_factory, user_factory):
    usuario = user_factory()
    futura = actividad_factory(estado=ESTADO_PUBLICADA)
    borrador = actividad_factory(estado="borrador")
    inscribir(db_session, futura.id, usuario.id)
    db_session.add(
        Inscripcion(actividad_id=borrador.id, user_id=usuario.id, estado=INSCRIPCION_ALTA)
    )
    db_session.commit()

    assert my_actividades(db_session, usuario.id) == [futura]