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
    cerrar_ventana_asistencia,
    asegurar_ventana_asistencia,
    mark_present_manual,
    present_user_ids,
    acreditar_creditos_pendientes,
)
from app.services.encuestas import estudiante_completo_encuesta
from app.services.credits import accumulated_credits
from app.services.inscripcion import inscribir


def test_attendance_window_has_stable_activity_code(
    db_session, actividad_factory
):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)

    primera = asegurar_ventana_asistencia(db_session, actividad.id)
    segunda = asegurar_ventana_asistencia(db_session, actividad.id)

    assert primera.id == segunda.id
    assert primera.codigo == segunda.codigo
    assert primera.codigo_cierre == segunda.codigo_cierre


def test_enrollment_closure_emails_roster_qr_code_and_close_link(
    db_session, actividad_factory, user_factory, carrera_factory, monkeypatch
):
    from app.services import mailing

    career = carrera_factory(nombre="Ingeniería")
    teacher = user_factory(
        rol="docente", email="docente@example.com"
    )
    student = user_factory(email="alumno@example.com")
    student.nombre = "Ana"
    student.apellido = "Pérez"
    student.carrera_id = career.id
    activity = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    activity.docentes.append(teacher.docente)
    db_session.commit()
    inscribir(db_session, activity.id, student.id)
    activity.fecha_inicio = datetime.now(timezone.utc) + timedelta(hours=12)
    db_session.commit()

    sent = []

    def record_email(to, subject, body, *, attachments=None):
        sent.append((to, subject, body, attachments))
        return True

    monkeypatch.setattr(mailing, "send_email", record_email)
    now = datetime.now(timezone.utc)
    count = asistencia.process_closed_enrollment_attendance_emails(
        db_session, now=now
    )
    second_count = asistencia.process_closed_enrollment_attendance_emails(
        db_session, now=now
    )

    assert count == 1
    assert second_count == 0
    assert len(sent) == 1
    to, subject, body, attachments = sent[0]
    assert to == teacher.email
    assert subject == f"Inscripción cerrada: {activity.titulo}"
    assert "Nombre: Ana" in body
    assert "Apellido: Pérez" in body
    assert "Mail: alumno@example.com" in body
    assert "Carrera: Grado Ingeniería" in body
    window = (
        db_session.query(asistencia.VentanaAsistencia)
        .filter_by(actividad_id=activity.id)
        .one()
    )
    assert window.codigo in body
    assert window.codigo_cierre in body
    assert len(attachments) == 1
    assert attachments[0][0] == f"asistencia-{activity.id}.png"
    assert attachments[0][2] == "image/png"


def test_check_in_registra_asistencia_para_usuario_inscripto(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        encuesta_obligatoria=False,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    actividad.fecha_inicio = datetime.now(timezone.utc) + timedelta(minutes=20)
    actividad.fecha_fin = actividad.fecha_inicio + timedelta(hours=2)
    db_session.commit()
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    resultado = check_in(db_session, f"  {window.codigo}  ", estudiante.id)

    assert resultado.id == actividad.id
    assert present_user_ids(db_session, actividad.id) == {estudiante.id}
    assert db_session.query(Asistencia).one().validated_by is None
    assert accumulated_credits(db_session, estudiante.id) == actividad.creditos


def test_check_in_rechaza_codigo_valido_antes_de_30_minutos_del_inicio(
    db_session, actividad_factory, user_factory, monkeypatch
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    hora = actividad.fecha_inicio.replace(tzinfo=timezone.utc) - timedelta(minutes=31)
    monkeypatch.setattr(asistencia, "_now", lambda: hora)
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    with pytest.raises(AsistenciaError, match="no está abierta"):
        check_in(db_session, window.codigo, estudiante.id)


def test_check_in_acepta_codigo_valido_dentro_de_ventana_hasta_seis_horas_del_fin(
    db_session, actividad_factory, user_factory, monkeypatch
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    hora = actividad.fecha_inicio.replace(tzinfo=timezone.utc) + timedelta(hours=5)
    monkeypatch.setattr(asistencia, "_now", lambda: hora)
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    resultado = check_in(db_session, window.codigo, estudiante.id)

    assert resultado.id == actividad.id
    assert present_user_ids(db_session, actividad.id) == {estudiante.id}


def test_check_in_rechaza_codigo_valido_despues_de_seis_horas_del_fin(
    db_session, actividad_factory, user_factory, monkeypatch
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    hora = actividad.fecha_inicio.replace(tzinfo=timezone.utc) + timedelta(
        hours=6, seconds=1
    )
    monkeypatch.setattr(asistencia, "_now", lambda: hora)
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    with pytest.raises(AsistenciaError, match="no está abierta"):
        check_in(db_session, window.codigo, estudiante.id)


def test_check_in_defers_credits_until_survey_then_releases_once(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        creditos=3,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    docente = user_factory(rol="docente")
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    actividad.fecha_inicio = datetime.now(timezone.utc) + timedelta(minutes=20)
    actividad.fecha_fin = actividad.fecha_inicio + timedelta(hours=2)
    db_session.commit()
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    check_in(db_session, window.codigo, estudiante.id)

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
        estado=ESTADO_PUBLICADA,
        encuesta_obligatoria=False,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    actividad.fecha_inicio = datetime.now(timezone.utc) + timedelta(minutes=20)
    actividad.fecha_fin = actividad.fecha_inicio + timedelta(hours=2)
    db_session.commit()
    window = asegurar_ventana_asistencia(db_session, actividad.id)

    check_in(db_session, window.codigo, estudiante.id)

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

    with pytest.raises(AsistenciaError, match=mensaje):
        check_in(db_session, token, user_factory().id)


def test_check_in_rechaza_expirado_no_inscripto_y_duplicado(
    db_session, actividad_factory, user_factory, monkeypatch
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    estudiante = user_factory()
    inscribir(db_session, actividad.id, estudiante.id)
    ahora = actividad.fecha_inicio.replace(tzinfo=timezone.utc) - timedelta(minutes=10)
    monkeypatch.setattr(asistencia, "_now", lambda: ahora)
    window = asegurar_ventana_asistencia(db_session, actividad.id)
    no_inscripto = user_factory()

    with pytest.raises(AsistenciaError, match="No estás inscripto"):
        check_in(db_session, window.codigo, no_inscripto.id)

    check_in(db_session, window.codigo, estudiante.id)

    with pytest.raises(AsistenciaError, match="ya fue registrada"):
        check_in(db_session, window.codigo, estudiante.id)


def test_cerrar_ventana_asistencia_invalidates_activity_code(
    db_session, actividad_factory, monkeypatch
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    window = asegurar_ventana_asistencia(db_session, actividad.id)
    ahora = actividad.fecha_inicio.replace(tzinfo=timezone.utc)
    monkeypatch.setattr(asistencia, "_now", lambda: ahora)
    assert asistencia.ventana_asistencia_abierta(actividad, window)

    assert cerrar_ventana_asistencia(db_session, window.codigo_cierre)

    db_session.refresh(window)
    assert not asistencia.ventana_asistencia_abierta(actividad, window)
    assert not cerrar_ventana_asistencia(db_session, window.codigo_cierre)


def test_cerrar_ventana_asistencia_rejected_before_activity_starts(
    db_session, actividad_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    window = asegurar_ventana_asistencia(db_session, actividad.id)
    inicio = actividad.fecha_inicio.replace(tzinfo=timezone.utc)

    assert not cerrar_ventana_asistencia(
        db_session,
        window.codigo_cierre,
        now=inicio - timedelta(seconds=1),
    )
    db_session.refresh(window)
    assert not window.cerrada_manualmente
    assert cerrar_ventana_asistencia(
        db_session, window.codigo_cierre, now=inicio
    )


def test_attendance_window_uses_start_time_boundaries(
    db_session, actividad_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
    )
    window = asegurar_ventana_asistencia(db_session, actividad.id)
    inicio = actividad.fecha_inicio.replace(tzinfo=timezone.utc)

    assert asistencia.ventana_asistencia_abierta(
        actividad, window, now=inicio - timedelta(minutes=30)
    )
    assert asistencia.ventana_asistencia_abierta(
        actividad, window, now=inicio + timedelta(hours=5, minutes=59)
    )
    assert not asistencia.ventana_asistencia_abierta(
        actividad, window, now=inicio + timedelta(hours=6)
    )


def test_mark_present_manual_valida_estudiante_inscripto(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(
        estado=ESTADO_PUBLICADA,
        encuesta_obligatoria=False,
        fecha_inicio=datetime.now(timezone.utc) + timedelta(days=2),
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