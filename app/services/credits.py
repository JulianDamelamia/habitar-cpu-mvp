"""Credits & progress service (E-07)."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Actividad, AppConfig, Asistencia


def required_credits(db: Session) -> int:
    row = db.get(AppConfig, "required_credits")
    if row and row.value.isdigit():
        return int(row.value)
    return settings.REQUIRED_CREDITS


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
    req = required_credits(db)
    pct = min(round(acc / req * 100), 100) if req else 0
    return {"accumulated": acc, "required": req, "pct": pct, "complete": acc >= req}
