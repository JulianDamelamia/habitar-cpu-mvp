"""Asistencia service (E-05). Docente opens a rotating-token session; student checks in."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Asistencia,
    SesionAsistencia,
    ESTADO_PUBLICADA,
    ROLE_ESTUDIANTE,
    User,
)
from app.services.inscripcion import is_enrolled

TOKEN_TTL_SECONDS = 90


class AsistenciaError(Exception):
    pass


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

    db.add(
        Asistencia(
            actividad_id=sess.actividad_id,
            user_id=user_id,
            validated_by=sess.created_by,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Concurrent double-scan: the unique constraint already recorded it.
        db.rollback()
        raise AsistenciaError("Tu asistencia ya fue registrada.")
    return db.get(Actividad, sess.actividad_id)


def present_user_ids(db: Session, actividad_id: int) -> set[int]:
    rows = db.query(Asistencia.user_id).filter(Asistencia.actividad_id == actividad_id).all()
    return {r[0] for r in rows}


def mark_present_manual(db: Session, actividad_id: int, user_id: int, validated_by: int) -> None:
    """Admin/docente manual override (E-09 supervision).

    Mirrors the guards in check_in(): the target must be a real student enrolled
    in the actividad, so asistencia/credits cannot be fabricated for arbitrary ids.
    """
    target = db.get(User, user_id)
    if target is None or target.role != ROLE_ESTUDIANTE:
        raise AsistenciaError("El usuario indicado no es un estudiante válido.")
    if not is_enrolled(db, actividad_id, user_id):
        raise AsistenciaError("El estudiante no está inscripto en esta actividad.")
    exists = (
        db.query(Asistencia)
        .filter(Asistencia.actividad_id == actividad_id, Asistencia.user_id == user_id)
        .first()
    )
    if exists:
        return
    db.add(Asistencia(actividad_id=actividad_id, user_id=user_id, validated_by=validated_by))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
