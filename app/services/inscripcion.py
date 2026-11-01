"""Inscripcion service (E-03). Cupo enforced transactionally with a row lock."""
from __future__ import annotations
import io
from datetime import datetime, timedelta, timezone

from fastapi import UploadFile
import pandas as pd
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    ESTADO_PUBLICADA,
    Estudiante,
    Inscripcion,
    INSCRIPCION_BAJA,
    INSCRIPCION_ALTA,
    User,
)
from app.services.asistencia import present_user_ids
from app.services.consultas_comunes import asistencia_validada, active_enrollment
from app.services.notifications import notify
from app.services.parsing import to_utc_datetime

class EnrollError(Exception):
    pass

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
    if actividad.inscripcion_cerrada:
        raise EnrollError("La inscripción a esta actividad ya está cerrada.")
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


def cancellation_penalty_applies(
    actividad: Actividad, *, now: datetime | None = None
) -> bool:
    current_time = to_utc_datetime(now or datetime.now(timezone.utc))
    fecha_inicio = to_utc_datetime(actividad.fecha_inicio)
    fecha_fin = to_utc_datetime(actividad.fecha_fin)
    return (
        current_time < fecha_inicio
        and current_time < fecha_fin
        and fecha_inicio - current_time < timedelta(hours=24)
    )


def unenroll(
    db: Session,
    actividad_id: int,
    user_id: int,
    *,
    now: datetime | None = None,
) -> bool:
    enr = active_enrollment(db, actividad_id, user_id)
    if not enr:
        raise EnrollError("No estás inscripto en esta actividad.")
    actividad = db.get(Actividad, actividad_id)
    estudiante = db.get(Estudiante, user_id)
    user = db.get(User, user_id)
    if actividad is None or estudiante is None or user is None:
        raise EnrollError("No se pudo procesar la baja del estudiante.")
    current_time = to_utc_datetime(now or datetime.now(timezone.utc))
    if to_utc_datetime(actividad.fecha_fin) <= current_time:
        raise EnrollError("No podés darte de baja de una actividad ya finalizada.")

    asistencia = asistencia_validada(db, actividad_id, user_id)
    if asistencia:
        raise EnrollError("No podés darte de baja de una actividad ya completada.")

    penalizar = cancellation_penalty_applies(actividad, now=now)

    enr.estado = INSCRIPCION_BAJA
    if penalizar:
        estudiante.creditos_penalizacion += 1.0
        notify(
            db,
            user,
            (
                f"Penalización de 1 crédito requerido por baja tardía de "
                f"'{actividad.titulo}': cancelación con menos de 24 horas "
                "de anticipación."
            ),
        )
    db.commit()
    return penalizar


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


def inscriptos_dataframe(db: Session, actividad_id: int) -> pd.DataFrame:
    inscriptos_actividad = inscriptos(db, actividad_id)
    presentes = present_user_ids(db, actividad_id)
    rows = [
        {
            "apellido": enrollment.user.apellido,
            "nombre": enrollment.user.nombre,
            "email": enrollment.user.email,
            "asistio": "sí" if enrollment.user_id in presentes else "no",
        }
        for enrollment in inscriptos_actividad
    ]
    return pd.DataFrame(rows, columns=["apellido", "nombre", "email", "asistio"])

async def leer_tabla_usuarios(archivo:UploadFile)-> pd.DataFrame:
    raw = await archivo.read()
    if archivo.filename.lower().endswith(".xlsx"): # type: ignore
        df = pd.read_excel(io.BytesIO(raw))
    df = pd.read_csv(io.BytesIO(raw))
    return df

COLUMNAS_ESPERADAS = {'email', 'nombre', 'apellido'}
def validar_datos_usuarios(df:pd.DataFrame) -> None:
    """Validación síncrona de columnas y formatos."""
    cols = {str(c).lower().strip() for c in df.columns}
    if cols != COLUMNAS_ESPERADAS:
        faltantes = COLUMNAS_ESPERADAS - cols
        raise ValueError(f"El archivo debe contener las columnas {faltantes}.")
    