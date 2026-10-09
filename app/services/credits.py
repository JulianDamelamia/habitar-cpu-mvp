"""Credits & progress service (E-07)."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Asistencia,
    ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
    Estudiante,
)


def required_credits(db: Session, user_id: int) -> float:
    estudiante = db.get(Estudiante, user_id)
    if estudiante is None:
        return 0.0
    return estudiante.creditos_requeridos + estudiante.creditos_penalizacion


def accumulated_credits(db: Session, user_id: int) -> float:
    estudiante = db.get(Estudiante, user_id)
    return estudiante.creditos_acreditados if estudiante else 0.0


def completed_actividades(db: Session, user_id: int) -> list[tuple[Actividad, object]]:
    rows = (
        db.query(Actividad, Asistencia.validated_at)
        .join(Asistencia, Asistencia.actividad_id == Actividad.id)
        .filter(Asistencia.user_id == user_id)
        .order_by(Asistencia.validated_at.desc())
        .all()
    )
    return [(r[0], r[1]) for r in rows]


def pending_survey_activities(db: Session, user_id: int) -> list[Actividad]:
    return (
        db.query(Actividad)
        .join(Asistencia, Asistencia.actividad_id == Actividad.id)
        .filter(
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .order_by(Actividad.fecha_inicio.desc())
        .all()
    )


def progress(db: Session, user_id: int) -> dict:
    acc = accumulated_credits(db, user_id)
    req = required_credits(db, user_id)
    pct = min(round(acc / req * 100), 100) if req else 0
    pending = (
        db.query(func.coalesce(func.sum(Actividad.creditos), 0))
        .join(Asistencia, Asistencia.actividad_id == Actividad.id)
        .filter(
            Asistencia.user_id == user_id,
            Asistencia.estado_creditos == ESTADO_CREDITOS_PENDIENTE_ENCUESTA,
        )
        .scalar()
    )
    pending = float(pending or 0)
    pending_pct = min(round(pending / req * 100), 100 - pct) if req else 0
    return {
        "accumulated": acc,
        "required": req,
        "pct": pct,
        "pending": pending,
        "pending_pct": pending_pct,
        "complete": acc >= req,
    }
