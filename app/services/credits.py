"""Credits & progress service (E-07)."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Actividad, Asistencia, Carrera, User


def required_credits(db: Session, user_id: int) -> int:
    required = (
        db.query(Carrera.creditos_requeridos)
        .join(User, User.carrera_id == Carrera.id)
        .filter(User.id == user_id)
        .scalar()
    )
    return int(required or 0)


def accumulated_credits(db: Session, user_id: int) -> int:
    total = (
        db.query(func.coalesce(func.sum(Actividad.creditos), 0))
        .join(Asistencia, Asistencia.actividad_id == Actividad.id)
        .filter(Asistencia.user_id == user_id)
        .scalar()
    )
    return int(total or 0)


def completed_actividades(db: Session, user_id: int) -> list[tuple[Actividad, object]]:
    rows = (
        db.query(Actividad, Asistencia.validated_at)
        .join(Asistencia, Asistencia.actividad_id == Actividad.id)
        .filter(Asistencia.user_id == user_id)
        .order_by(Asistencia.validated_at.desc())
        .all()
    )
    return [(r[0], r[1]) for r in rows]


def progress(db: Session, user_id: int) -> dict:
    acc = accumulated_credits(db, user_id)
    req = required_credits(db, user_id)
    pct = min(round(acc / req * 100), 100) if req else 0
    return {"accumulated": acc, "required": req, "pct": pct, "complete": acc >= req}
