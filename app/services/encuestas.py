"""Survey completion checks used by post-activity credit awards."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Actividad, SurveyResponse


def estudiante_completo_encuesta(
    db: Session, estudiante_id: int, actividad_id: int
) -> bool:
    actividad = db.get(Actividad, actividad_id)
    if actividad is None:
        return False
    if not actividad.encuesta_obligatoria:
        return True
    return (
        db.query(SurveyResponse.id)
        .filter(
            SurveyResponse.user_id == estudiante_id,
            SurveyResponse.actividad_id == actividad_id,
        )
        .first()
        is not None
    )
