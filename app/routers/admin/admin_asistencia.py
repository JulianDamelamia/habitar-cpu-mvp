from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models import Actividad, User
from app.security import REQUIERE_ADMIN
from app.templating import render

router = APIRouter()


def _render_asistencia(
    request: Request,
    actividad: Actividad,
    user: User,
    db: Session,
    *,
    mensaje: str | None = None,
    error: str | None = None,
) -> Response:
    inscriptos = services.inscripcion.inscriptos(db, actividad.id)
    present = services.asistencia.present_user_ids(db, actividad.id)
    return render(
        request,
        "admin/asistencia.html",
        user=user,
        db=db,
        a=actividad,
        inscriptos=inscriptos,
        present=present,
        mensaje=mensaje,
        error=error,
    )


@router.get("/{actividad_id}/asistencia", name="admin_asistencia")
def admin_asistencia(
    request: Request,
    actividad_id: int,
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    actividad = services.actividades.get(db, actividad_id)
    if actividad is None:
        return render(
            request,
            "admin/asistencia.html",
            user=user,
            db=db,
            a=None,
            inscriptos=[],
            present=set(),
            error="Actividad no encontrada.",
        )
    return _render_asistencia(request, actividad, user, db)


@router.post(
    "/{actividad_id}/asistencia/{student_id}/marcar",
    name="admin_marcar_asistencia",
)
def admin_marcar_asistencia(
    request: Request,
    actividad_id: int,
    student_id: int,
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    actividad = services.actividades.get(db, actividad_id)
    if actividad is None:
        return render(
            request,
            "admin/asistencia.html",
            user=user,
            db=db,
            a=None,
            inscriptos=[],
            present=set(),
            error="Actividad no encontrada.",
        )
    try:
        credited = services.asistencia.mark_present_manual(
            db, actividad_id, student_id, user.id
        )
    except services.asistencia.AsistenciaError as exc:
        return _render_asistencia(request, actividad, user, db, error=str(exc))
    mensaje = (
        "Asistencia registrada y créditos acreditados."
        if credited
        else "Asistencia registrada. El estudiante debe responder la encuesta para recibir los créditos."
    )
    return _render_asistencia(request, actividad, user, db, mensaje=mensaje)


@router.post(
    "/{actividad_id}/asistencia/{student_id}/revocar",
    name="admin_revocar_asistencia",
)
def admin_revocar_asistencia(
    request: Request,
    actividad_id: int,
    student_id: int,
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    actividad = services.actividades.get(db, actividad_id)
    if actividad is None:
        return render(
            request,
            "admin/asistencia.html",
            user=user,
            db=db,
            a=None,
            inscriptos=[],
            present=set(),
            error="Actividad no encontrada.",
        )
    revoked = services.asistencia.revoke_present(db, actividad_id, student_id)
    if not revoked:
        return _render_asistencia(
            request,
            actividad,
            user,
            db,
            error="El estudiante no tenía asistencia registrada.",
        )
    return _render_asistencia(
        request,
        actividad,
        user,
        db,
        mensaje="Asistencia revocada.",
    )
