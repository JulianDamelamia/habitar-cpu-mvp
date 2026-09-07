"""Actividad catalogue service (E-02 discovery, E-08 admin CRUD)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.models import (
    Actividad,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Carrera
)


def get(db: Session, actividad_id: int) -> Actividad | None:
    return db.get(Actividad, actividad_id)


def inscriptos_count(db: Session, actividad_id: int) -> int:
    return (
        db.query(Inscripcion)
        .filter(Inscripcion.actividad_id == actividad_id, Inscripcion.estado == INSCRIPCION_ALTA)
        .count()
    )


def cupo_info(db: Session, actividad: Actividad) -> dict:
    taken = inscriptos_count(db, actividad.id)
    return {
        "taken": taken,
        "free": max(actividad.cupo_max - taken, 0),
        "full": taken >= actividad.cupo_max,
    }


def list_published(
    db: Session,
    *,
    tipo: str | None = None,
    fecha: str | None = None,
    min_creditos: int | None = None,
    solo_disponibles: bool = False,
) -> list[Actividad]:
    stmt = select(Actividad).where(Actividad.estado == ESTADO_PUBLICADA)
    if tipo:
        stmt = stmt.where(Actividad.tipo == tipo)
    if min_creditos:
        stmt = stmt.where(Actividad.creditos >= min_creditos)
    if fecha:
        try:
            day = datetime.fromisoformat(fecha).date()
            stmt = stmt.where(func.date(Actividad.fecha_inicio) == day)
        except ValueError:
            pass
    stmt = stmt.order_by(Actividad.fecha_inicio.asc())
    actividades = list(db.execute(stmt).scalars().all())
    if solo_disponibles:
        actividades = [a for a in actividades if not cupo_info(db, a)["full"]]
    return actividades


def list_all(db: Session) -> list[Actividad]:
    return list(
        db.execute(select(Actividad).order_by(Actividad.fecha_inicio.desc())).scalars().all()
    )


def create(db: Session, **fields) -> Actividad:
    # 1. Separar la lógica de carreras antes de instanciar Actividad(**fields)
    actividad = Actividad(**fields)
    db.add(actividad)
    db.commit()
    db.refresh(actividad)
    return actividad


def update(db: Session, actividad: Actividad, **fields) -> Actividad:
    for key, value in fields.items():
        setattr(actividad, key, value)
    db.commit()
    db.refresh(actividad)
    return actividad
