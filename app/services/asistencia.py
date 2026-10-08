"""Asistencia service (E-05). Docente opens a rotating-token session; student checks in."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Asistencia,
    ESTADO_CREDITOS_ACREDITADO,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    Estudiante,
    SesionAsistencia,
    ROL_ESTUDIANTE,
    User,
)
from app.services.encuestas import estudiante_completo_encuesta
from app.services.consultas_comunes import is_enrolled

TOKEN_TTL_SECONDS = 90


class AsistenciaError(Exception):
    pass


def _acreditar_creditos(
    db: Session, actividad_id: int, user_id: int, cantidad: float
) -> bool:
    attendance = (
        db.query(Asistencia)
        .filter(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
        )
        .one_or_none()
    )
    if attendance is None:
        raise AsistenciaError("No se encontró la asistencia para acreditar.")
    if attendance.estado_creditos == ESTADO_CREDITOS_ACREDITADO:
        return True
    if attendance.estado_creditos != ESTADO_CREDITOS_PENDIENTE_ENCUESTA:
        raise AsistenciaError("La asistencia tiene un estado de créditos inválido.")
    if not estudiante_completo_encuesta(db, user_id, actividad_id):
        return False

    marked = db.execute(
        update(Asistencia)
        .where(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .values(estado_creditos=ESTADO_CREDITOS_ACREDITADO)
    )
    if marked.rowcount != 1:
        attendance = (
            db.query(Asistencia)
            .filter(
                Asistencia.actividad_id == actividad_id,
                Asistencia.user_id == user_id,
            )
            .one_or_none()
        )
        if attendance is None:
            raise AsistenciaError("No se encontró la asistencia para acreditar.")
        return attendance.estado_creditos == ESTADO_CREDITOS_ACREDITADO

    result = db.execute(
        update(Estudiante)
        .where(Estudiante.user_id == user_id)
        .values(creditos_acreditados=Estudiante.creditos_acreditados + cantidad)
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
        if _acreditar_creditos(db, actividad_id, user_id, actividad.creditos):
            acreditados += actividad.creditos
    return acreditados


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_token() -> str:
    # 6-digit code embedded in the QR; short, human-typable as fallback.
    return f"{secrets.randbelow(1_000_000):06d}"


def current_session(db: Session, actividad_id: int) -> SesionAsistencia | None:
    sess = (
        db.query(SesionAsistencia)
        .filter(SesionAsistencia.actividad_id == actividad_id)
        .order_by(SesionAsistencia.created_at.desc())
        .first()
    )
    return sess


def open_or_rotate(db: Session, actividad_id: int, docente_id: int) -> SesionAsistencia:
    """Return a live session, rotating the token if expired or absent."""
    sess = current_session(db, actividad_id)
    expires = _now() + timedelta(seconds=TOKEN_TTL_SECONDS)
    if sess is None:
        sess = SesionAsistencia(
            actividad_id=actividad_id,
            token=_unique_token(db),
            expires_at=expires,
            created_by=docente_id,
        )
        db.add(sess)
    else:
        exp = sess.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= _now():
            sess.token = _unique_token(db)
            sess.expires_at = expires
            sess.created_by = docente_id
    db.commit()
    db.refresh(sess)
    return sess


def _unique_token(db: Session) -> str:
    for _ in range(10):
        token = _new_token()
        if not db.query(SesionAsistencia).filter(SesionAsistencia.token == token).first():
            return token
    return secrets.token_hex(4)


def check_in(db: Session, token: str, user_id: int) -> Actividad:
    """Validate a scanned token and mark the student present. Raises AsistenciaError."""
    token = token.strip()
    sess = db.query(SesionAsistencia).filter(SesionAsistencia.token == token).first()
    if sess is None:
        raise AsistenciaError("Código inválido.")
    exp = sess.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= _now():
        raise AsistenciaError("El código expiró. Pedile al docente que muestre uno nuevo.")

    if not is_enrolled(db, sess.actividad_id, user_id):
        raise AsistenciaError("No estás inscripto en esta actividad.")

    already = (
        db.query(Asistencia)
        .filter(Asistencia.actividad_id == sess.actividad_id, Asistencia.user_id == user_id)
        .first()
    )
    if already:
        raise AsistenciaError("Tu asistencia ya fue registrada.")
    actividad = db.get(Actividad, sess.actividad_id)
    if actividad is None:
        raise AsistenciaError("No se pudo actualizar el registro de créditos del estudiante.")

    db.add(
        Asistencia(
            actividad_id=sess.actividad_id,
            user_id=user_id,
            validated_by=sess.created_by,
            estado_creditos=ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
    )
    try:
        db.flush()
        _acreditar_creditos(db, sess.actividad_id, user_id, actividad.creditos)
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
