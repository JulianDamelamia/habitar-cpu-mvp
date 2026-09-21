"""Actividad catalogue service (E-02 discovery, E-08 admin CRUD)."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    ESTADO_BORRADOR,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Carrera
)
from .carreras import get_carreras_desde_dropdown

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
    carrera_id: list[int] | None = None,
    tipo: str | None = None,
    fecha: str | None = None,
    min_creditos: int | None = None,
    solo_disponibles: bool = False,
) -> list[Actividad]:
    #si es estudiante, habrá una lista de ids (puede ser vacía)
    #si no es estudiante, carreras_ids es None

    #caso estudiante no tiene asignada ninguna carrera, early return
    if carrera_id is None: 
        return []

    stmt = select(Actividad).where(Actividad.estado == ESTADO_PUBLICADA)

    if carrera_id:
        stmt = stmt.where(Actividad.carreras_asociadas.any(Carrera.id == carrera_id))
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


def list_all(db: Session, carreras_ids: list[str] | None = None) -> list[Actividad]:
    stmt = select(Actividad)
    if carreras_ids and "todas" not in carreras_ids:
        ids = [int(cid) for cid in carreras_ids if cid.isdigit()]
        if ids:
            stmt = stmt.filter(Actividad.carreras_asociadas.any(Carrera.id.in_(ids)))

    return list(
        db.execute(stmt.order_by(Actividad.fecha_inicio.desc())).scalars().all()
    )


def create(db: Session, **fields) -> Actividad:
    carreras_asociadas = fields.get("carreras_asociadas") or []
    if not carreras_asociadas:
        fields["estado"] = ESTADO_BORRADOR
    actividad = Actividad(**fields)
    db.add(actividad)
    db.commit()
    db.refresh(actividad)
    return actividad


def update(db: Session, actividad: Actividad, **fields) -> Actividad:
    carreras_asociadas = fields.get("carreras_asociadas", actividad.carreras_asociadas)
    if not carreras_asociadas:
        fields["estado"] = ESTADO_BORRADOR
    for key, value in fields.items():
        setattr(actividad, key, value)
    db.commit()
    db.refresh(actividad)
    return actividad
