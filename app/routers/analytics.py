"""E-10 Analytics & reports dashboard (coordination + director)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import requiere_roles
from app.services import analytics as analytics_svc
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
        overview=analytics_svc.overview(db),
        top=analytics_svc.top_actividades(db),
        per_actividad=analytics_svc.asistencia_per_actividad(db),
        surveys=analytics_svc.survey_averages(db),
    )
