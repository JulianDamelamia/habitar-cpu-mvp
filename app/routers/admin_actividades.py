"""E-08 Actividad management (coordination backoffice)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Actividad,
    Inscripcion,
    INSCRIPCION_ALTA,
    ESTADO_BORRADOR,
    ESTADO_CANCELADA,
    ESTADO_PUBLICADA,
    ROL_DOCENTE,
    TIPO_PRESENCIAL,
    TIPO_VIRTUAL,
    User,
)
from app.notifications import notify
from app.security import requiere_roles
from app.services import actividades as actividades_svc
from app.services import inscripcion as enrollment_svc
from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")


def _parse_dt(value: str) -> datetime:
    # datetime-local -> naive; store as UTC-aware (wall-clock kept for display).
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _parse_dates(fecha_inicio: str, fecha_fin: str) -> tuple[datetime, datetime]:
    """Parse both dates and validate order. Raises ValueError on malformed/invalid input."""
    inicio = _parse_dt(fecha_inicio)
    fin = _parse_dt(fecha_fin)
    if fin < inicio:
        raise ValueError("La fecha de fin es anterior al inicio.")
    return inicio, fin


def _docentes(db: Session) -> list[User]:
    return db.query(User).filter(User.rol == ROL_DOCENTE).order_by(User.apellido).all()


@router.get("/admin")
def panel(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    items = actividades_svc.list_all(db)
    rows = [{"a": a, "cupo": actividades_svc.cupo_info(db, a)} for a in items]
    resumen = {
        "publicadas": sum(1 for a in items if a.estado == ESTADO_PUBLICADA),
        "borradores": sum(1 for a in items if a.estado == ESTADO_BORRADOR),
        "total": len(items),
        "inscripciones": sum(r["cupo"]["taken"] for r in rows),
    }
    return render(request, "admin/panel.html", user=user, db=db, rows=rows, resumen=resumen)


@router.get("/admin/actividades/nueva")
def nueva(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    return render(
        request, "admin/form.html", user=user, db=db,
        a=None, docentes=_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
    )


@router.post("/admin/actividades")
def crear(
    request: Request,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    tipo: str = Form(TIPO_PRESENCIAL),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    lugar: str = Form(""),
    docente_id: str = Form(""),
    creditos: int = Form(1),
    cupo_max: int = Form(30),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
):
    try:
        inicio, fin = _parse_dates(fecha_inicio, fecha_fin)
    except ValueError:
        return RedirectResponse(url="/admin?err=Fechas inválidas: revisá inicio y fin.", status_code=303)
    actividades_svc.create(
        db,
        titulo=titulo.strip(), descripcion=descripcion.strip(), tipo=tipo,
        fecha_inicio=inicio, fecha_fin=fin,
        lugar=lugar.strip(), docente_id=int(docente_id) if docente_id.isdigit() else None,
        creditos=creditos, cupo_max=cupo_max, estado=ESTADO_BORRADOR, created_by=user.id,
    )
    return RedirectResponse(url="/admin?msg=Actividad creada como borrador.", status_code=303)


@router.get("/admin/actividades/{actividad_id}/editar")
def editar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    return render(
        request, "admin/form.html", user=user, db=db,
        a=a, docentes=_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
    )


@router.post("/admin/actividades/{actividad_id}")
def actualizar(
    request: Request,
    actividad_id: int,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    tipo: str = Form(TIPO_PRESENCIAL),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    lugar: str = Form(""),
    docente_id: str = Form(""),
    creditos: int = Form(1),
    cupo_max: int = Form(30),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    try:
        inicio, fin = _parse_dates(fecha_inicio, fecha_fin)
    except ValueError:
        return RedirectResponse(url="/admin?err=Fechas inválidas: revisá inicio y fin.", status_code=303)
    was_published = a.estado == ESTADO_PUBLICADA
    fecha_cambio = a.fecha_inicio != inicio
    actividades_svc.update(
        db, a,
        titulo=titulo.strip(), descripcion=descripcion.strip(), tipo=tipo,
        fecha_inicio=inicio, fecha_fin=fin,
        lugar=lugar.strip(), docente_id=int(docente_id) if docente_id.isdigit() else None,
        creditos=creditos, cupo_max=cupo_max,
    )
    if fecha_cambio:
        # Cambió la fecha de inicio: re-armar el recordatorio de 24h de los inscriptos.
        db.query(Inscripcion).filter(
            Inscripcion.actividad_id == actividad_id,
            Inscripcion.estado == INSCRIPCION_ALTA,
        ).update({Inscripcion.reminded: False})
        db.commit()
    if was_published:
        # Best-effort notifications; the actividad update is already committed.
        try:
            for enr in enrollment_svc.inscriptos(db, actividad_id):
                notify(
                    db, enr.user,
                    f"La actividad '{a.titulo}' fue actualizada. Revisá los nuevos datos (fecha {a.fecha_inicio.strftime('%d/%m/%Y %H:%M')}).",
                    email_subject="Cambios en una actividad inscripta",
                )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    return RedirectResponse(url="/admin?msg=Actividad actualizada.", status_code=303)


@router.get("/admin/actividades/{actividad_id}/preview")
def preview(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    return render(request, "admin/preview.html", user=user, db=db, a=a, cupo=actividades_svc.cupo_info(db, a))


@router.post("/admin/actividades/{actividad_id}/publicar")
def publicar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    actividades_svc.update(db, a, estado=ESTADO_PUBLICADA)
    return RedirectResponse(url="/admin?msg=Actividad publicada. Ya es visible para los estudiantes.", status_code=303)


@router.post("/admin/actividades/{actividad_id}/cancelar")
def cancelar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    actividades_svc.update(db, a, estado=ESTADO_CANCELADA)
    return RedirectResponse(url="/admin?msg=Actividad cancelada.", status_code=303)
