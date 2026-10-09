"""Actividad catalogue service (E-02 discovery, E-08 admin CRUD)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Docente,
    ESTADO_BORRADOR,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Carrera
)
from .carreras import get_carreras_desde_dropdown


def validar_creditos(valor: object) -> Decimal:
    try:
        creditos = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError("Los créditos deben ser un número válido.") from None
    if not creditos.is_finite() or creditos <= 0 or creditos * 2 != (creditos * 2).to_integral_value():
        raise ValueError("Los créditos deben ser mayores a 0 y múltiplo de 0,5.")
    return creditos


def resolver_docentes(
    db: Session,
    *,
    docentes_ids: list[int],
    nombres: list[str],
    apellidos: list[str],
) -> list[Docente]:
    if len(nombres) != len(apellidos):
        raise ValueError("Cada docente nuevo debe tener nombre y apellido.")

    nombres_limpios = [" ".join(nombre.split()) for nombre in nombres]
    apellidos_limpios = [" ".join(apellido.split()) for apellido in apellidos]
    for nombre, apellido in zip(nombres_limpios, apellidos_limpios):
        if bool(nombre) != bool(apellido):
            raise ValueError("Ingresá nombre y apellido para cada docente nuevo.")

    docentes = []
    if docentes_ids:
        encontrados = db.query(Docente).filter(Docente.id.in_(set(docentes_ids))).all()
        if len(encontrados) != len(set(docentes_ids)):
            raise ValueError("Uno o más docentes seleccionados no existen.")
        docentes.extend(encontrados)

    por_nombre = {
        (" ".join(d.nombre.split()).casefold(), " ".join(d.apellido.split()).casefold()): d
        for d in db.query(Docente).all()
    }
    for nombre, apellido in zip(nombres_limpios, apellidos_limpios):
        if not nombre and not apellido:
            continue
        clave = (nombre.casefold(), apellido.casefold())
        docente = por_nombre.get(clave)
        if docente is None:
            docente = Docente(nombre=nombre, apellido=apellido)
            db.add(docente)
            por_nombre[clave] = docente
        docentes.append(docente)
    return list({docente.id if docente.id is not None else id(docente): docente for docente in docentes}.values())


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


def ordenar_actividades(
    db: Session,
    actividades: list[Actividad],
    *,
    orden: str | None,
    direccion: str | None,
) -> list[Actividad]:
    if orden not in {"nombre", "fecha", "cupo", "estado"}:
        return actividades

    sentido = direccion if direccion in {"asc", "desc"} else {
        "nombre": "asc",
        "fecha": "desc",
        "cupo": "desc",
        "estado": "asc",
    }[orden]
    datos = {actividad.id: cupo_info(db, actividad) for actividad in actividades}

    # Stable passes retain tie-break order: title, date, state, then free seats.
    actividades.sort(key=lambda actividad: -datos[actividad.id]["free"])
    actividades.sort(
        key=lambda actividad: {
            ESTADO_PUBLICADA: 0,
            ESTADO_BORRADOR: 1,
        }.get(actividad.estado, 2)
    )
    actividades.sort(key=lambda actividad: actividad.fecha_inicio, reverse=True)
    actividades.sort(key=lambda actividad: actividad.titulo.casefold())

    primary_key = {
        "nombre": lambda actividad: actividad.titulo.casefold(),
        "fecha": lambda actividad: actividad.fecha_inicio,
        "cupo": lambda actividad: datos[actividad.id]["free"],
        "estado": lambda actividad: {
            ESTADO_PUBLICADA: 0,
            ESTADO_BORRADOR: 1,
        }.get(actividad.estado, 2),
    }[orden]
    actividades.sort(key=primary_key, reverse=sentido == "desc")
    return actividades


def list_published(
    db: Session,
    *,
    carrera_id: list[int] | None = None,
    tipo: str | None = None,
    fecha: str | None = None,
    min_creditos: Decimal | None = None,
    solo_disponibles: bool = False,
    orden: str | None = None,
    direccion: str | None = None,
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
    actividades = list(db.execute(stmt).scalars().all())
    if solo_disponibles:
        actividades = [a for a in actividades if not cupo_info(db, a)["full"]]
    if orden:
        return ordenar_actividades(
            db, actividades, orden=orden, direccion=direccion
        )
    return sorted(actividades, key=lambda actividad: actividad.fecha_inicio)


def list_all(
    db: Session,
    carreras_ids: list[str] | None = None,
    *,
    orden: str | None = None,
    direccion: str | None = None,
) -> list[Actividad]:
    stmt = select(Actividad)
    if carreras_ids and "todas" not in carreras_ids:
        ids = [int(cid) for cid in carreras_ids if cid.isdigit()]
        if ids:
            stmt = stmt.filter(Actividad.carreras_asociadas.any(Carrera.id.in_(ids)))

    actividades = list(db.execute(stmt).scalars().all())
    if orden:
        return ordenar_actividades(
            db, actividades, orden=orden, direccion=direccion
        )
    return sorted(actividades, key=lambda actividad: actividad.fecha_inicio, reverse=True)


def create(db: Session, **fields) -> Actividad:
    if "creditos" in fields:
        fields["creditos"] = validar_creditos(fields["creditos"])
    carreras_asociadas = fields.get("carreras_asociadas") or []
    if not carreras_asociadas:
        fields["estado"] = ESTADO_BORRADOR
    actividad = Actividad(**fields)
    db.add(actividad)
    db.commit()
    db.refresh(actividad)
    return actividad


def update(db: Session, actividad: Actividad, **fields) -> Actividad:
    if "creditos" in fields:
        fields["creditos"] = validar_creditos(fields["creditos"])
    carreras_asociadas = fields.get("carreras_asociadas", actividad.carreras_asociadas)
    if not carreras_asociadas:
        fields["estado"] = ESTADO_BORRADOR
    for key, value in fields.items():
        setattr(actividad, key, value)
    db.commit()
    db.refresh(actividad)
    return actividad
