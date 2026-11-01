"""Actividad catalogue service (E-02 discovery, E-08 admin CRUD)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Docente,
    ESTADO_CANCELADA,
    ESTADO_BORRADOR,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Carrera,
    Persona,
)


@dataclass(frozen=True)
class DocentesInput:
    ids: list[int]
    nombres: list[str]
    apellidos: list[str]
    emails: list[str]


@dataclass(frozen=True)
class ActividadContext:
    titulo: str
    descripcion: str
    tipo: str
    fecha_inicio: datetime
    fecha_fin: datetime
    lugar: str
    docentes: list[Docente]
    creditos: Decimal
    cupo_max: int
    encuesta_obligatoria: bool
    carreras_asociadas: list[Carrera]


def validar_creditos(valor: object) -> Decimal:
    '''Valida que el valor de créditos sea un número positivo y múltiplo de 0,5.'''
    try:
        creditos = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError("Los créditos deben ser un número válido.") from None
    if not creditos.is_finite() or creditos <= 0 or creditos * 2 != (creditos * 2).to_integral_value():
        raise ValueError("Los créditos deben ser mayores a 0 y múltiplo de 0,5.")
    return creditos


def resolver_docentes(
    db: Session,
    datos: DocentesInput,
) -> list[Docente]:
    docentes_ids = datos.ids
    nombres = datos.nombres
    apellidos = datos.apellidos
    emails = datos.emails

    if len(nombres) != len(apellidos) or len(nombres) != len(emails) or len(apellidos) != len(emails):
        raise ValueError("Cada docente nuevo debe tener nombre, apellido y mail.")

    nombres_limpios = [" ".join(nombre.split()) for nombre in nombres]
    apellidos_limpios = [" ".join(apellido.split()) for apellido in apellidos]
    emails_limpios = [" ".join(email.split()).lower() for email in emails]
    for nombre, apellido, email in zip(nombres_limpios, apellidos_limpios, emails_limpios):
        if bool(nombre) != bool(apellido) or bool(nombre) != bool(email) or bool(apellido) != bool(email):
            raise ValueError("Ingresá nombre, apellido y email para cada docente nuevo.")

    docentes = []
    if docentes_ids:
        encontrados = db.query(Docente).filter(Docente.id.in_(set(docentes_ids))).all()
        if len(encontrados) != len(set(docentes_ids)):
            raise ValueError("Uno o más docentes seleccionados no existen.")
        docentes.extend(encontrados)

    por_nombre = {
        (" ".join(d.persona.nombre.split()).casefold(), " ".join(d.persona.apellido.split()).casefold()): d
        for d in db.query(Docente).all()
        if d.persona is not None
    }
    for nombre, apellido, email in zip(nombres_limpios, apellidos_limpios, emails_limpios):
        if not nombre and not apellido:
            continue
        clave = (nombre.casefold(), apellido.casefold())
        personas = (
            db.query(Persona)
            .filter(func.lower(Persona.email) == email)
            .all()
        )
        if len(personas) > 1:
            raise ValueError("El email está asociado a más de una persona.")

        persona = personas[0] if personas else None
        docente = por_nombre.get(clave)
        if persona is not None:
            nombre_persona = " ".join(persona.nombre.split()).casefold()
            apellido_persona = " ".join(persona.apellido.split()).casefold()
            if (nombre_persona, apellido_persona) != clave:
                raise ValueError("El email ya está asociado a otra persona.")
            if persona.usuario is not None and persona.docente is None:
                raise ValueError("El email ya está asociado a una cuenta de usuario.")
            docente = persona.docente or Docente(persona=persona)
            db.add(docente)
        elif docente is not None:
            if docente.persona.email:
                email_existente = docente.persona.email.strip().lower()
                if email_existente != email:
                    raise ValueError(
                        "El docente ya tiene otro email asociado; seleccioná el docente existente."
                    )
            else:
                docente.persona.email = email
        else:
            persona = Persona(nombre=nombre, apellido=apellido, email=email)
            docente = Docente(persona=persona)
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

    if orden == "estado":
        actividades.sort(key=lambda actividad: actividad.titulo.casefold())
        actividades.sort(key=lambda actividad: actividad.fecha_inicio, reverse=True)
        actividades.sort(
            key=_clave_estado_actividad, reverse=sentido == "desc"
        )
        return actividades

    if orden == "cupo":
        actividades.sort(key=lambda actividad: actividad.titulo.casefold())
        actividades.sort(key=lambda actividad: actividad.fecha_inicio, reverse=True)
        actividades.sort(
            key=lambda actividad: datos[actividad.id]["free"],
            reverse=sentido == "desc",
        )
        actividades.sort(key=_clave_estado_actividad)
        return actividades

    # Keep date and name ordering stable with status and capacity tie-breakers.
    actividades.sort(key=lambda actividad: -datos[actividad.id]["free"])
    actividades.sort(key=_clave_estado_actividad)
    actividades.sort(key=lambda actividad: actividad.fecha_inicio, reverse=True)
    actividades.sort(key=lambda actividad: actividad.titulo.casefold())

    primary_key = {
        "nombre": lambda actividad: actividad.titulo.casefold(),
        "fecha": lambda actividad: actividad.fecha_inicio,
    }[orden]
    actividades.sort(key=primary_key, reverse=sentido == "desc")
    return actividades


def _clave_estado_actividad(actividad: Actividad) -> int:
    if actividad.estado == ESTADO_PUBLICADA:
        return 1 if actividad.finalizada else 0
    if actividad.finalizada:
        return 3
    if actividad.estado == ESTADO_CANCELADA:
        return 2
    return 4


def listar_disponibles(
    db: Session,
    *,
    carrera_id: list[int] | None = None,
    tipo: str | None = None,
    fecha: str | None = None,
    min_creditos: Decimal | None = None,
    solo_con_cupo: bool = False,
    orden: str | None = None,
    direccion: str | None = None,
) -> list[Actividad]:
    '''Lista las actividades disponibles para inscripción, filtrando por carrera, tipo, fecha y créditos mínimos.'''
    #si es estudiante, habrá una lista de ids (puede ser vacía)
    #si no es estudiante, carreras_ids es None
    #caso estudiante no tiene asignada ninguna carrera, early return
    if carrera_id is None: 
        return []

    stmt = select(Actividad).where(
        Actividad.estado == ESTADO_PUBLICADA
        and not Actividad.finalizada 
        and not Actividad.inscripcion_cerrada)

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
    if solo_con_cupo:
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


def create(
    db: Session,
    contexto: ActividadContext,
    *,
    created_by: int | None = None,
) -> Actividad:
    estado = (
        ESTADO_BORRADOR
        if not contexto.carreras_asociadas
        else ESTADO_PUBLICADA
    )
    actividad = Actividad(
        titulo=contexto.titulo,
        descripcion=contexto.descripcion,
        tipo=contexto.tipo,
        fecha_inicio=contexto.fecha_inicio,
        fecha_fin=contexto.fecha_fin,
        lugar=contexto.lugar,
        docentes=contexto.docentes,
        creditos=validar_creditos(contexto.creditos),
        cupo_max=contexto.cupo_max,
        encuesta_obligatoria=contexto.encuesta_obligatoria,
        carreras_asociadas=contexto.carreras_asociadas,
        estado=estado,
        created_by=created_by,
    )
    db.add(actividad)
    db.commit()
    db.refresh(actividad)
    return actividad


def update(
    db: Session,
    actividad: Actividad,
    contexto: ActividadContext,
) -> Actividad:
    actividad.titulo = contexto.titulo
    actividad.descripcion = contexto.descripcion
    actividad.tipo = contexto.tipo
    actividad.fecha_inicio = contexto.fecha_inicio
    actividad.fecha_fin = contexto.fecha_fin
    actividad.lugar = contexto.lugar
    actividad.docentes = contexto.docentes
    actividad.creditos = validar_creditos(contexto.creditos)
    actividad.cupo_max = contexto.cupo_max
    actividad.encuesta_obligatoria = contexto.encuesta_obligatoria
    actividad.carreras_asociadas = contexto.carreras_asociadas
    if not contexto.carreras_asociadas:
        actividad.estado = ESTADO_BORRADOR

    db.commit()
    db.refresh(actividad)
    return actividad


def update_estado(db: Session, actividad: Actividad, estado: str) -> Actividad:
    actividad.estado = estado
    db.commit()
    db.refresh(actividad)
    return actividad
