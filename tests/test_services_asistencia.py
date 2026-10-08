from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Asistencia,
    ESTADO_CREDITOS_ACREDITADO,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    ESTADO_PUBLICADA,
    SurveyResponse,
)
from app.services import asistencia
from app.services.asistencia import (
    AsistenciaError,
    check_in,
    current_session,
    mark_present_manual,
    open_or_rotate,
    present_user_ids,
    acreditar_creditos_pendientes,
)
from app.services.encuestas import estudiante_completo_encuesta
from app.services.credits import accumulated_credits
from app.services.inscripcion import inscribir


def test_open_or_rotate_crea_y_reutiliza_sesion(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    docente = user_factory(rol="docente")

    primera = open_or_rotate(db_session, actividad.id, docente.id)
    segunda = open_or_rotate(db_session, actividad.id, docente.id)

    assert primera.id == segunda.id
    assert primera.token == segunda.token
    assert current_session(db_session, actividad.id).id == primera.id


def test_open_or_rotate_renueva_sesion_expirada(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    docente = user_factory(rol="docente")
    sesion = open_or_rotate(db_session, actividad.id, docente.id)
    token_anterior = sesion.token
    sesion.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    renovada = open_or_rotate(db_session, actividad.id, docente.id)

    assert renovada.id == sesion.id
    assert renovada.token != token_anterior
    expires_at = renovada.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)


def test_check_in_registra_asistencia_para_usuario_inscripto(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA, encuesta_obligatoria=False
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    sesion = open_or_rotate(db_session, actividad.id, docente.id)

    resultado = check_in(db_session, f"  {sesion.token}  ", estudiante.id)

    assert resultado.id == actividad.id
    assert present_user_ids(db_session, actividad.id) == {estudiante.id}
    assert db_session.query(Asistencia).one().validated_by == docente.id
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos


def test_check_in_defers_credits_until_survey_then_releases_once(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA, creditos=3)
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    sesion = open_or_rotate(db_session, actividad.id, docente.id)

    check_in(db_session, sesion.token, estudiante.id)

    asistencia = db_session.query(Asistencia).one()
    assert asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA
    assert accumulated_credits(db_session, estudiante.id) == 0
    assert not estudiante_completo_encuesta(
        db_session, estudiante.id, actividad.id
    )

    db_session.add(
        SurveyResponse(
            actividad_id=actividad.id,
            user_id=estudiante.id,
            rating=5,
            comment=None,
        )
    )
    db_session.flush()
    assert estudiante_completo_encuesta(db_session, estudiante.id, actividad.id)
    assert acreditar_creditos_pendientes(
        db_session, actividad.id, estudiante.id
    ) == actividad.creditos
    db_session.commit()

    assert asistencia.estado_creditos == ESTADO_CREDITOS_ACREDITADO
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos
    assert acreditar_creditos_pendientes(
        db_session, actividad.id, estudiante.id
    ) == 0
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos


def test_survey_not_required_credits_are_awarded_immediately(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA, encuesta_obligatoria=False
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    sesion = open_or_rotate(db_session, actividad.id, docente.id)

    check_in(db_session, sesion.token, estudiante.id)

    asistencia = db_session.query(Asistencia).one()
    assert asistencia.estado_creditos == ESTADO_CREDITOS_ACREDITADO
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos
    assert estudiante_completo_encuesta(
        db_session, estudiante.id, actividad.id
    )


@pytest.mark.parametrize(
    "token, mensaje",
    [("000000", "inválido")],
)
def test_check_in_rechaza_token_invalido(db_session, actividad_factory, user_factory, token, mensaje):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    docente = user_factory(rol="docente")
    open_or_rotate(db_session, actividad.id, docente.id)

    with pytest.raises(AsistenciaError, match=mensaje):
        check_in(db_session, token, user_factory().id)


def test_check_in_rechaza_expirado_no_inscripto_y_duplicado(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    sesion = open_or_rotate(db_session, actividad.id, docente.id)
    sesion.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    with pytest.raises(AsistenciaError, match="expiró"):
        check_in(db_session, sesion.token, estudiante.id)

    sesion.expires_at = datetime.now(timezone.utc) + timedelta(seconds=90)
    db_session.commit()
    inscribir(db_session, actividad.id, estudiante.id)
    check_in(db_session, sesion.token, estudiante.id)

    with pytest.raises(AsistenciaError, match="ya fue registrada"):
        check_in(db_session, sesion.token, estudiante.id)


def test_mark_present_manual_valida_estudiante_inscripto(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA, encuesta_obligatoria=False
    )
    estudiante = user_factory()
    validador = user_factory(rol="docente")
    inscribir(db_session, actividad.id, estudiante.id)

    mark_present_manual(db_session, actividad.id, estudiante.id, validador.id)
    mark_present_manual(db_session, actividad.id, estudiante.id, validador.id)

    assert present_user_ids(db_session, actividad.id) == {estudiante.id}
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos


def test_mark_present_manual_rechaza_usuario_invalido_o_no_inscripto(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    docente = user_factory(rol="docente")
    estudiante = user_factory()

    with pytest.raises(AsistenciaError, match="no es un estudiante"):
        mark_present_manual(db_session, actividad.id, docente.id, docente.id)
    with pytest.raises(AsistenciaError, match="no está inscripto"):
        mark_present_manual(db_session, actividad.id, estudiante.id, docente.id)