"""Asistencia service: registro de asistencia y acreditación de créditos."""
from __future__ import annotations

import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import qrcode
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Asistencia,
    ESTADO_CREDITOS_ACREDITADO,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    ESTADO_PUBLICADA,
    Estudiante,
    ROL_ESTUDIANTE,
    User,
    VentanaAsistencia,
)
from app.services.encuestas import estudiante_completo_encuesta
from app.services.consultas_comunes import is_enrolled

class AsistenciaError(Exception):
    pass
        
    
def _acreditar_creditos(
    db: Session, actividad_id: int, user_id: int, cantidad: float
) -> bool:
    '''Comprueba si el estudiante ya tiene acreditados los créditos de la 
    actividad y, si no, si ha completado la encuesta los acredita.
    '''
    asistencia = (
        db.query(Asistencia)
        .filter(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
        )
        .one_or_none()
    )
    if asistencia is None:
        raise AsistenciaError("No se encontró la asistencia para acreditar.")
    
    # validar estado y early return si ya están acreditados
    if asistencia.estado_creditos == ESTADO_CREDITOS_ACREDITADO:
        return True
    
    if asistencia.estado_creditos != ESTADO_CREDITOS_PENDIENTE_ENCUESTA:
        raise AsistenciaError("La asistencia tiene un estado de créditos inválido.")

    # verificar completitud de la encuesta
    if not estudiante_completo_encuesta(db, user_id, actividad_id):
        return False
    
    # intentar actualizar el estado de la asistencia (con control de concurrencia)
    marked = db.execute(
        update(Asistencia)
        .where(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .values(estado_creditos=ESTADO_CREDITOS_ACREDITADO)
    )
    
    # si hubo un conflicto de concurrencia, re-verificar estado actual
    if marked.rowcount != 1:
        asistencia = (
            db.query(Asistencia)
            .filter(
                Asistencia.actividad_id == actividad_id,
                Asistencia.user_id == user_id,
            )
            .one_or_none()
        )
        if asistencia is None:
            raise AsistenciaError("No se encontró la asistencia para acreditar.")
        return asistencia.estado_creditos == ESTADO_CREDITOS_ACREDITADO
    
    # actualizar créditos del estudiante de forma segura
    result = db.execute(
        update(Estudiante)
        .where(Estudiante.user_id == user_id)
        .values(creditos_acreditados=Estudiante.creditos_acreditados + float(cantidad))
    )
    if result.rowcount != 1:
        raise AsistenciaError("No se pudo actualizar el registro de créditos del estudiante.")
        
    return True


def creditos_pendientes_encuesta(db: Session, actividad_id: int, user_id: int) -> bool:
    return (
        db.query(Asistencia.id)
        .filter(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .first()
        is not None
    )


def acreditar_creditos_pendientes(
    db: Session, actividad_id: int, user_id: int
) -> float:
    '''Acredita los créditos pendientes de encuesta para un estudiante en una actividad.
    Devuelve la cantidad de créditos acreditados (0.0 si no se acreditó nada).
    '''
    actividad = db.get(Actividad, actividad_id)
    if actividad is None:
        return 0.0
    pendientes = (
        db.query(Asistencia)
        .filter(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .all()
    )
    acreditados = 0.0
    for _ in pendientes:
        cantidad = float(actividad.creditos)
        if _acreditar_creditos(db, actividad_id, user_id, cantidad):
            acreditados += cantidad
    return acreditados


def _now() -> datetime:
    return datetime.now(timezone.utc)


def asegurar_ventana_asistencia(
    db: Session, actividad_id: int
) -> VentanaAsistencia:
    '''Asegura que exista una ventana de asistencia para la actividad, creándola si no existe.
    Devuelve la ventana existente o recién creada.
    '''
    window = (
        db.query(VentanaAsistencia)
        .filter(VentanaAsistencia.actividad_id == actividad_id)
        .one_or_none()
    )
    if window is not None:
        return window
    window = VentanaAsistencia(
        actividad_id=actividad_id,
        codigo=_codigo_asistencia_unico(db),
        codigo_cierre=secrets.token_urlsafe(48),
    )
    db.add(window)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        window = (
            db.query(VentanaAsistencia)
            .filter(VentanaAsistencia.actividad_id == actividad_id)
            .one_or_none()
        )
        if window is None:
            raise
    db.refresh(window)
    return window


def _codigo_asistencia_unico(db: Session) -> str:
    for _ in range(100):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if not db.query(VentanaAsistencia).filter(
            VentanaAsistencia.codigo == code
        ).first():
            return code
    raise RuntimeError("No se pudo generar un código de asistencia único.")


def cerrar_ventana_asistencia(
    db: Session,
    close_code: str,
    *,
    now: datetime | None = None,
) -> bool:
    '''Cierra manualmente la ventana de asistencia asociada al código de cierre.'''
    window = (
        db.query(VentanaAsistencia)
        .filter(VentanaAsistencia.codigo_cierre == close_code)
        .one_or_none()
    )
    if window is None or window.cerrada_manualmente:
        return False
    actividad = db.get(Actividad, window.actividad_id)
    if actividad is None or not puede_cerrar_ventana_asistencia(actividad, now=now):
        return False
    window.cerrada_manualmente = True
    db.commit()
    return True


def puede_cerrar_ventana_asistencia(
    actividad: Actividad, *, now: datetime | None = None
) -> bool:
    '''Indica si la ventana de asistencia puede cerrarse manualmente (E-09).'''
    inicio = actividad.fecha_inicio
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current >= inicio


def ventana_asistencia_abierta(
    actividad: Actividad,
    window: VentanaAsistencia,
    *,
    now: datetime | None = None,
) -> bool:
    '''Indica si la ventana de asistencia está abierta para registrar asistencia (E-09).'''
    if window.cerrada_manualmente:
        return False
    start = actividad.fecha_inicio
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return actividad.estado == ESTADO_PUBLICADA and (
        start - timedelta(minutes=30) <= current < start + timedelta(hours=6)
    )


def process_closed_enrollment_attendance_emails(
    db: Session, *, now: datetime | None = None
) -> int:
    from app.config import settings
    from app.models import ESTADO_PUBLICADA, INSCRIPCION_ALTA, Inscripcion
    from app.services.mailing import send_email

    current = now or _now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    activities = db.query(Actividad).filter(
        Actividad.estado == ESTADO_PUBLICADA
    ).all()
    delivered = 0
    for activity in activities:
        start = activity.fecha_inicio
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start > current + timedelta(hours=24):
            continue
        window = asegurar_ventana_asistencia(db, activity.id)
        notified_emails = set(json.loads(window.correos_enviados))
        teachers = {
            teacher_user.email: teacher_user
            for docente in activity.docentes
            for teacher_user in docente.usuarios
            if teacher_user.email
        }
        if not teachers:
            continue
        if set(teachers).issubset(notified_emails):
            continue
        enrollments = (
            db.query(Inscripcion)
            .filter(
                Inscripcion.actividad_id == activity.id,
                Inscripcion.estado == INSCRIPCION_ALTA,
            )
            .all()
        )
        roster = []
        for enrollment in enrollments:
            student = enrollment.user
            career = student.carrera
            career_name = (
                f"{career.tipo.nombre} {career.nombre}" if career else "Sin carrera"
            )
            roster.append(
                f"| {student.nombre} | {student.apellido} | {student.email} | {career_name} |"
            )
        close_url = (
            f"{settings.PUBLIC_BASE_URL}/docente/asistencia/cerrar/"
            f"{window.codigo_cierre}"
        )
        body = (
            f"Inscripción cerrada para '{activity.titulo}'.\n\n"
            f"Inicio: {activity.fecha_inicio.strftime('%d/%m/%Y %H:%M')}\n"
            f"Código de validación: {window.codigo}\n"
            f"Ventana de asistencia: desde 30 minutos antes del inicio hasta "
            "6 horas después del inicio.\n"
            f"Cierre manual: {close_url}\n\n"
            "Inscriptos:\n"
            + (
                "| Nombre | Apellido | Mail | Carrera |\n"
                "| --- | --- | --- | --- |\n"
                + "\n".join(roster)
                if roster
                else "- No hay inscriptos."
            )
        )
        qr_buffer = io.BytesIO()
        #TODO: En producción, guardar el QR en un directorio accesible y enviar la URL en lugar de adjuntar la imagen.
        #qrcode.make(window.codigo).save(qr_buffer, format="PNG") (esto iria en produ)
        qr_image = qrcode.make(window.codigo)
        qr_image.save(qr_buffer, format="PNG")
        qr_dir = Path("./data/qr")
        qr_dir.mkdir(parents=True, exist_ok=True)
        qr_image.save(qr_dir / f"asistencia-{activity.id}.png", format="PNG")
        
        attachment = (
            f"asistencia-{activity.id}.png",
            qr_buffer.getvalue(),
            "image/png",
        )
        for email in teachers:
            if email in notified_emails:
                continue
            if send_email(
                email,
                f"Inscripción cerrada: {activity.titulo}",
                body,
                attachments=[attachment],
            ):
                notified_emails.add(email)
                window.correos_enviados = json.dumps(sorted(notified_emails))
                db.commit()
                delivered += 1
    return delivered


def check_in(db: Session, token: str, user_id: int) -> Actividad:
    """Validate a scanned token and mark the student present. Raises AsistenciaError."""
    token = token.strip()
    window = (
        db.query(VentanaAsistencia)
        .filter(VentanaAsistencia.codigo == token)
        .one_or_none()
    )
    if window is None:
        raise AsistenciaError("Código inválido.")
    actividad = db.get(Actividad, window.actividad_id)
    if actividad is None or not ventana_asistencia_abierta(actividad, window):
        raise AsistenciaError("La actividad no está abierta para registrar asistencia.")
    if not is_enrolled(db, window.actividad_id, user_id):
        raise AsistenciaError("No estás inscripto en esta actividad.")

    already = (
        db.query(Asistencia)
        .filter(
            Asistencia.actividad_id == window.actividad_id,
            Asistencia.user_id == user_id,
        )
        .first()
    )
    if already:
        raise AsistenciaError("Tu asistencia ya fue registrada.")

    db.add(
        Asistencia(
            actividad_id=window.actividad_id,
            user_id=user_id,
            validated_by=None,
            estado_creditos=ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
    )
    try:
        db.flush()
        _acreditar_creditos(db, window.actividad_id, user_id, actividad.creditos)
        db.commit()
    except IntegrityError:
        # Concurrent double-scan: the unique constraint already recorded it.
        db.rollback()
        raise AsistenciaError("Tu asistencia ya fue registrada.")
    return actividad


def present_user_ids(db: Session, actividad_id: int) -> set[int]:
    rows = db.query(Asistencia.user_id).filter(Asistencia.actividad_id == actividad_id).all()
    return {r[0] for r in rows}

def mark_present_manual(
    db: Session, actividad_id: int, user_id: int, validated_by: int
) -> bool:
    """Admin/docente manual override (E-09 supervision).

    Mirrors the guards in check_in(): the target must be a real student enrolled
    in the actividad, so asistencia/credits cannot be fabricated for arbitrary ids.
    """
    target = db.get(User, user_id)
    if target is None or target.rol != ROL_ESTUDIANTE:
        raise AsistenciaError("El usuario indicado no es un estudiante válido.")
    actividad = db.get(Actividad, actividad_id)
    if actividad is None:
        raise AsistenciaError("No se pudo actualizar el registro de créditos del estudiante.")
    if not is_enrolled(db, actividad_id, user_id):
        raise AsistenciaError("El estudiante no está inscripto en esta actividad.")
    existing = (
        db.query(Asistencia)
        .filter(Asistencia.actividad_id == actividad_id, Asistencia.user_id == user_id)
        .first()
    )
    if existing:
        credited = _acreditar_creditos(
            db, actividad_id, user_id, actividad.creditos
        )
        db.commit()
        return credited
    attendance = Asistencia(
        actividad_id=actividad_id,
        user_id=user_id,
        validated_by=validated_by,
        estado_creditos=ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    )
    db.add(attendance)
    try:
        db.flush()
        credited = _acreditar_creditos(db, actividad_id, user_id, actividad.creditos)
        db.commit()
        return credited
    except IntegrityError:
        db.rollback()
        return False


def revoke_present(db: Session, actividad_id: int, user_id: int) -> bool:
    """Remove a student's attendance and reverse credits already awarded for it."""
    attendance = (
        db.query(Asistencia)
        .filter(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
        )
        .one_or_none()
    )
    if attendance is None:
        return False
    if attendance.estado_creditos == ESTADO_CREDITOS_ACREDITADO:
        actividad = db.get(Actividad, actividad_id)
        estudiante = db.get(Estudiante, user_id)
        if actividad is None or estudiante is None:
            raise AsistenciaError("No se pudieron revertir los créditos de la asistencia.")
        estudiante.creditos_acreditados -= float(actividad.creditos)
        if estudiante.creditos_acreditados < 0:
            raise AsistenciaError("No se pudieron revertir los créditos de la asistencia.")
    db.delete(attendance)
    db.commit()
    return True
