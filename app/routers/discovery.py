"""E-02 Discovery & exploration of actividades (student-facing)."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.templating import _TemplateResponse

from app.database import get_db
from app.models import TIPO_PRESENCIAL, TIPO_VIRTUAL, User
from app.security import current_user_required
from app import services
from app.templating import build_sort_links, redirect_to, render

router = APIRouter()


@router.get("/actividades")
def list_actividades(
    request: Request,
    tipo: str = "",
    fecha: str = "",
    min_creditos: str = "",
    solo_disponibles: str = "",
    sort: str = "",
    direction: str = "",
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db)
) -> _TemplateResponse:
    sort = sort if sort in {"nombre", "fecha", "cupo"} else ""
    defaults = {"nombre": "asc", "fecha": "desc", "cupo": "desc"}
    direction = direction if direction in {"asc", "desc"} else defaults.get(sort, "")
    try:
        min_cred = Decimal(min_creditos) if min_creditos else None
    except InvalidOperation:
        min_cred = None
    if min_cred is not None and (not min_cred.is_finite() or min_cred < 0.5):
        min_cred = None
    items = services.actividades.list_published(
        db,
        carrera_id=user.carrera_id,
        tipo=tipo or None,
        fecha=fecha or None,
        min_creditos=min_cred,
        solo_disponibles=bool(solo_disponibles),
        orden=sort or None,
        direccion=direction or None,
    )
    enrolled_ids = {a.id for a in services.inscripcion.my_actividades(db, user.id)}
    rows = [{"a": a, "cupo": services.actividades.cupo_info(db, a), "enrolled": a.id in enrolled_ids} for a in items]
    return render(
        request, "student/actividades.html", user=user, db=db,
        rows=rows,
        filtros={"tipo": tipo, "fecha": fecha, "min_creditos": min_creditos, "solo_disponibles": solo_disponibles,},
        tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
        sort=sort,
        direction=direction,
        sort_links=build_sort_links(
            request,
            "list_actividades",
            ("nombre", "fecha", "cupo"),
            sort,
            direction,
            defaults,
        ),
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
        return redirect_to(
            request, "list_actividades",
            query_params={"err": "La actividad no está disponible."},
        )

    cupo = services.actividades.cupo_info(db, actividad)
    enrolled = services.consultas_comunes.is_enrolled(db, actividad_id, user.id)
    asistencia_validada = services.consultas_comunes.asistencia_validada(db, actividad_id, user.id)
    penalizacion_baja = (
        enrolled
        and not asistencia_validada
        and services.inscripcion.cancellation_penalty_applies(actividad)
    )
    return render(
        request, "student/detalle.html", user=user, db=db,
        a=actividad, cupo=cupo, enrolled=enrolled,
        asistencia_validada=asistencia_validada,
        penalizacion_baja=penalizacion_baja,
    )
