"""Analytics service (E-10). Aggregates for the coordination/director dashboard."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Actividad,
    Asistencia,
    ESTADO_PUBLICADA,
    Inscripcion,
    ENROLL_INSCRIPTO,
    SurveyResponse,
)


def overview(db: Session) -> dict:
    publicadas = db.query(Actividad).filter(Actividad.estado == ESTADO_PUBLICADA).count()
    inscripciones = db.query(Inscripcion).filter(Inscripcion.estado == ENROLL_INSCRIPTO).count()
    asistencias = db.query(Asistencia).count()
    rate = round(asistencias / inscripciones * 100, 1) if inscripciones else 0.0
    return {
        "actividades_publicadas": publicadas,
        "inscripciones": inscripciones,
        "asistencias": asistencias,
        "asistencia_rate": rate,
    }


def top_actividades(db: Session, limit: int = 5) -> list[dict]:
    rows = (
        db.query(Actividad.titulo, func.count(Inscripcion.id).label("n"))
        .join(Inscripcion, Inscripcion.actividad_id == Actividad.id)
        .filter(Inscripcion.estado == ENROLL_INSCRIPTO)
        .group_by(Actividad.id, Actividad.titulo)
        .order_by(func.count(Inscripcion.id).desc())
        .limit(limit)
        .all()
    )
    return [{"titulo": r[0], "inscriptos": int(r[1])} for r in rows]


def asistencia_per_actividad(db: Session) -> list[dict]:
    """Published actividades that have at least one enrollment (skip empty/draft ones)."""
    result = []
    actividades = (
        db.query(Actividad)
        .filter(Actividad.estado == ESTADO_PUBLICADA)
        .order_by(Actividad.fecha_inicio.desc())
        .all()
    )
    for a in actividades:
        insc = (
            db.query(Inscripcion)
            .filter(Inscripcion.actividad_id == a.id, Inscripcion.estado == ENROLL_INSCRIPTO)
            .count()
        )
        if insc == 0:
            continue
        asis = db.query(Asistencia).filter(Asistencia.actividad_id == a.id).count()
        result.append(
            {
                "titulo": a.titulo,
                "inscriptos": insc,
                "asistencias": asis,
                "rate": round(asis / insc * 100, 1) if insc else 0.0,
            }
        )
    return result


def survey_averages(db: Session) -> list[dict]:
    rows = (
        db.query(
            Actividad.titulo,
            func.avg(SurveyResponse.rating).label("avg"),
            func.count(SurveyResponse.id).label("n"),
        )
        .join(SurveyResponse, SurveyResponse.actividad_id == Actividad.id)
        .group_by(Actividad.id, Actividad.titulo)
        .order_by(func.avg(SurveyResponse.rating).desc())
        .all()
    )
    return [
        {"titulo": r[0], "promedio": round(float(r[1]), 2), "respuestas": int(r[2])}
        for r in rows
    ]
