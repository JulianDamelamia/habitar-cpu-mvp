from __future__ import annotations
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.asistencia import Asistencia
from app.models.inscripcion import Inscripcion
from app.models.enums import INSCRIPCION_ALTA

#Tuve que hacer este módulo de consultas para romper una importación circular
# TODO: revisar arquitectura y ver bien cómo organizar los módulos
# capaz hacer funciones proxy en los módulos solo para organizar los contenidos?

def asistencia_validada(db: Session, actividad_id: int, user_id: int)-> bool:
    stmt = select(
        exists().where(
            Asistencia.actividad_id == actividad_id,
            Asistencia.user_id == user_id
        )
    )
    asistencia_registrada = db.scalars(stmt).one() #en vez de db.scalar() para que pylance no chille
    return asistencia_registrada

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
