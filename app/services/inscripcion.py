"""Inscripcion service (E-03). Cupo enforced transactionally with a row lock."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_BAJA,
    INSCRIPCION_ALTA,
)


class EnrollError(Exception):
    pass


def active_enrollment(db: Session, actividad_id: int, user_id: int) -> Inscripcion | None:
    return (
        db.query(Inscripcion)
        .filter(
            Inscripcion.actividad_id == actividad_id,
            Inscripcion.user_id == user_id,
            Inscripcion.estado == INSCRIPCION_ALTA,
        )
        .first()
    )


def is_enrolled(db: Session, actividad_id: int, user_id: int) -> bool:
    return active_enrollment(db, actividad_id, user_id) is not None


def inscribir(db: Session, actividad_id: int, user_id: int) -> Actividad:
    """Atomically inscribir a user, respecting cupo. Raises EnrollError on failure."""
    # Lock the actividad row so concurrent enrolls serialise on cupo.
    actividad = db.execute(
        select(Actividad).where(Actividad.id == actividad_id).with_for_update()
    ).scalar_one_or_none()
    if actividad is None:
        raise EnrollError("La actividad no existe.")
    if actividad.estado != ESTADO_PUBLICADA:
        raise EnrollError("La actividad no está disponible para inscripción.")

    existing = (
        db.query(Inscripcion)
        .filter(Inscripcion.actividad_id == actividad_id, Inscripcion.user_id == user_id)
        .first()
    )
    if existing and existing.estado == INSCRIPCION_ALTA:
        raise EnrollError("Ya estás inscripto en esta actividad.")

    taken = (
        db.query(Inscripcion)
        .filter(Inscripcion.actividad_id == actividad_id, Inscripcion.estado == INSCRIPCION_ALTA)
        .count()
    )
    if taken >= actividad.cupo_max:
        db.rollback()
        raise EnrollError("No quedan cupos disponibles.")

    if existing:
        existing.estado = INSCRIPCION_ALTA
        existing.reminded = False  # re-arm the 24h reminder after a baja/re-inscripción
    else:
        db.add(Inscripcion(actividad_id=actividad_id, user_id=user_id, estado=INSCRIPCION_ALTA))
    db.commit()
    return actividad


def unenroll(db: Session, actividad_id: int, user_id: int) -> None:
    enr = active_enrollment(db, actividad_id, user_id)
    if not enr:
        raise EnrollError("No estás inscripto en esta actividad.")
    enr.estado = INSCRIPCION_BAJA
    db.commit()


def my_actividades(db: Session, user_id: int) -> list[Actividad]:
    rows = (
        db.query(Actividad)
        .join(Inscripcion, Inscripcion.actividad_id == Actividad.id)
        .filter(
            Inscripcion.user_id == user_id,
            Inscripcion.estado == INSCRIPCION_ALTA,
            Actividad.estado == ESTADO_PUBLICADA,
        )
        .order_by(Actividad.fecha_inicio.asc())
        .all()
    )
    return list(rows)


def inscriptos(db: Session, actividad_id: int) -> list[Inscripcion]:
    return (
        db.query(Inscripcion)
        .filter(Inscripcion.actividad_id == actividad_id, Inscripcion.estado == INSCRIPCION_ALTA)
        .all()
    )
