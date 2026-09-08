"""E-02 Discovery & exploration of actividades (student-facing)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import TIPO_PRESENCIAL, TIPO_VIRTUAL, User
from app.security import current_user_required
from app import services
from app.templating import render

router = APIRouter()


@router.get("/actividades")
def list_actividades(
    request: Request,
    tipo: str = "",
    fecha: str = "",
    min_creditos: str = "",
    solo_disponibles: str = "",
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    min_cred = int(min_creditos) if min_creditos.isdigit() else None
    items = services.actividades.list_published(
        db,
        tipo=tipo or None,
        fecha=fecha or None,
        min_creditos=min_cred,
        solo_disponibles=bool(solo_disponibles),
    )
    enrolled_ids = {a.id for a in services.inscripcion.my_actividades(db, user.id)}
    rows = [{"a": a, "cupo": services.actividades.cupo_info(db, a), "enrolled": a.id in enrolled_ids} for a in items]
    return render(
        request, "student/actividades.html", user=user, db=db,
        rows=rows,
        filtros={"tipo": tipo, "fecha": fecha, "min_creditos": min_creditos, "solo_disponibles": solo_disponibles},
        tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
    )


@router.get("/actividades/{actividad_id}")
def actividad_detail(
    request: Request,
    actividad_id: int,
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    actividad = services.actividades.get(db, actividad_id)
    if actividad is None or actividad.estado != "publicada":
        return RedirectResponse(url="/actividades?err=La actividad no está disponible.", status_code=303)
    cupo = services.actividades.cupo_info(db, actividad)
    enrolled = services.inscripcion.is_enrolled(db, actividad_id, user.id)
    return render(
        request, "student/detalle.html", user=user, db=db,
        a=actividad, cupo=cupo, enrolled=enrolled,
    )
