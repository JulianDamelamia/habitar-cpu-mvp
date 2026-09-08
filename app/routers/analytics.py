"""E-10 Analytics & reports dashboard (coordination + director)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User
from app.security import requiere_roles
from app import services
from app.templating import render

router = APIRouter()


@router.get("/analytics")
def dashboard(
    request: Request,
    user: User = Depends(requiere_roles("director", "coordinacion")),
    db: Session = Depends(get_db),
):
    return render(
        request, "analytics/dashboard.html", user=user, db=db,
        overview=services.analytics.overview(db),
        top=services.analytics.top_actividades(db),
        per_actividad=services.analytics.asistencia_per_actividad(db),
        surveys=services.analytics.survey_averages(db),
    )
