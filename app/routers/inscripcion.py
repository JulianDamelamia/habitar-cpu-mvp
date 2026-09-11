"""E-03 Inscription, E-04 'Mis próximas actividades', E-07 progress, in-app notifications."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, User
from app.services.notifications import notify
from app.security import current_user_required, requiere_roles
from app import services
from app.templating import render

router = APIRouter()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.post("/actividades/{actividad_id}/inscribir")
def inscribir(
    request: Request,
    actividad_id: int,
    user: User = Depends(requiere_roles("estudiante")),
    db: Session = Depends(get_db),
):
    try:
        actividad = services.inscripcion.inscribir(db, actividad_id, user.id)
    except services.inscripcion.EnrollError as exc:
        return RedirectResponse(url=f"/actividades/{actividad_id}?err={quote(str(exc))}", status_code=303)
    # Inscripcion is already durably committed by inscribir(); the confirmation
    # notification is best-effort and must not fail the (successful) inscription.
    try:
        notify(
            db, user,
            f"Inscripción confirmada: '{actividad.titulo}' el {actividad.fecha_inicio.strftime('%d/%m/%Y %H:%M')} en {actividad.lugar or 'el campus'}.",
            email_subject="Confirmación de inscripción",
        )
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
    return RedirectResponse(url=f"/actividades/{actividad_id}?msg=¡Inscripción confirmada! Te enviamos un mail.", status_code=303)


@router.post("/actividades/{actividad_id}/baja")
def baja(
    request: Request,
    actividad_id: int,
    user: User = Depends(requiere_roles("estudiante")),
    db: Session = Depends(get_db),
):
    try:
        services.inscripcion.unenroll(db, actividad_id, user.id)
    except services.inscripcion.EnrollError as exc:
        return RedirectResponse(url=f"/actividades/{actividad_id}?err={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"/actividades/{actividad_id}?msg=Te diste de baja. Liberaste tu cupo.", status_code=303)


@router.get("/home")
def home(
    request: Request,
    user: User = Depends(requiere_roles("estudiante")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    mine = services.inscripcion.my_actividades(db, user.id)
    proximas = [a for a in mine if _aware(a.fecha_fin) >= now]
    progreso = services.credits.progress(db, user.id)
    historial = services.credits.completed_actividades(db, user.id)
    return render(
        request, "student/home.html", user=user, db=db,
        proximas=proximas, progreso=progreso, historial=historial,
    )


@router.get("/notificaciones")
def notificaciones(
    request: Request,
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    items = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    # Mark all as read on view.
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.leido.is_(False)
    ).update({Notification.leido: True})
    db.commit()
    return render(request, "shared/notificaciones.html", user=user, db=db, items=items)
