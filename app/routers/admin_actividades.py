"""E-08 Actividad management (coordination backoffice)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
from typing import List, Literal

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session,contains_eager
from starlette.templating import _TemplateResponse

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
    TipoCarrera,
    User,
    Carrera
)
from app.services.notifications import notify
from app.security import requiere_roles
from app import services 

from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")

def _parse_dt(value: str) -> datetime:
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}", value or ""):
        raise ValueError("La fecha debe tener formato AAAA-MM-DDTHH:MM.")
    # datetime-local -> naive; store as UTC-aware (wall-clock kept for display).
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _parse_duration(value: str) -> timedelta:
    if not re.fullmatch(r"\d{2}:\d{2}", value.strip()):
        raise ValueError("La duración debe tener formato HH:MM.")
    try:
        hours_text, minutes_text = value.strip().split(":", 1)
        hours = int(hours_text)
        minutes = int(minutes_text)
    except ValueError:
        raise ValueError("La duración debe tener formato HH:MM.") from None
    if hours > 25 or not 0 <= minutes < 60 or hours == 0 and minutes == 0:
        raise ValueError("La duración debe ser mayor que 00:00 y tener minutos válidos.")
    return timedelta(hours=hours, minutes=minutes)


def _parse_dates(
    fecha_inicio: str,
    fecha_fin: str = "",
    duracion: str = "",
    modo_finalizacion: str = "duracion",
) -> tuple[datetime, datetime]:
    """Parse both dates and validate order. Raises ValueError on malformed/invalid input."""
    inicio = _parse_dt(fecha_inicio)
    if modo_finalizacion == "duracion":
        if duracion:
            fin = inicio + _parse_duration(duracion)
        else:
            # Compatibility with clients that still submit an explicit end date.
            fin = _parse_dt(fecha_fin)
    elif modo_finalizacion == "fecha_fin":
        fin = _parse_dt(fecha_fin)
    else:
        raise ValueError("Modo de finalización inválido.")
    hoy = datetime.now(timezone.utc).date()
    if inicio.date() < hoy or fin.date() < hoy:
        raise ValueError("Las fechas no pueden ser anteriores al día de hoy.")
    if fin < inicio:
        raise ValueError("La fecha de fin es anterior al inicio.")
    return inicio, fin


def _format_duration(inicio: datetime, fin: datetime) -> str:
    total_minutes = max(0, int((fin - inicio).total_seconds() // 60))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _docentes(db: Session) -> list[User]:
    return db.query(User).filter(User.rol == ROL_DOCENTE).order_by(User.apellido).all()


@router.get("/admin")
def panel(request: Request,carreras_asociadas: list[str] = Query([]), user: User = Depends(ADMIN), db: Session = Depends(get_db)) -> _TemplateResponse:
    items = services.actividades.list_all(db, carreras_ids=carreras_asociadas)
    rows = [{"a": a, "cupo": services.actividades.cupo_info(db, a)} for a in items]
    resumen = {
        "publicadas": sum(1 for a in items if a.estado == ESTADO_PUBLICADA),
        "borradores": sum(1 for a in items if a.estado == ESTADO_BORRADOR),
        "total": len(items),
        "inscripciones": sum(r["cupo"]["taken"] for r in rows),
    }
    lista_carreras = services.carreras.get_carreras(db)
    return render(
        request,
        "admin/panel.html",
        user=user,
        db=db,
        rows=rows,
        resumen=resumen,
        lista_carreras=lista_carreras,
        carreras_seleccionadas=carreras_asociadas
    )


@router.get("/admin/actividades/nueva")
def nueva(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    return render(
        request, "admin/form.html", user=user, db=db,
        a=None, docentes=_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
        lista_carreras=services.carreras.get_carreras(db),
        duracion_inicial="01:00",
        fecha_hoy=date.today().isoformat(),
    )


@router.post("/admin/actividades")
def crear(
    request: Request,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    tipo: str = Form(TIPO_PRESENCIAL),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(""),
    duracion: str = Form(""),
    modo_finalizacion: str = Form("duracion"),
    lugar: str = Form(""),
    docente_id: str = Form(""),
    creditos: int = Form(1),
    cupo_max: int = Form(30),
    carreras_asociadas: list[str] = Form([]),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        inicio, fin = _parse_dates(fecha_inicio, fecha_fin, duracion, modo_finalizacion)
    except ValueError:
        return RedirectResponse(url="/admin?err=Fechas inválidas: revisá inicio y fin.", status_code=303)
    carreras_asociadas_list = services.carreras.get_carreras_desde_dropdown(carreras_asociadas, db)      
    services.actividades.create(
        db,
        titulo=titulo.strip(), descripcion=descripcion.strip(), tipo=tipo,
        fecha_inicio=inicio, fecha_fin=fin, lugar=lugar.strip(),
        docente_id=int(docente_id) if docente_id.isdigit() else None,
        creditos=creditos, cupo_max=cupo_max, estado=ESTADO_BORRADOR, created_by=user.id,
        carreras_asociadas=carreras_asociadas_list,
    )
    return RedirectResponse(url="/admin?msg=Actividad creada como borrador.", status_code=303)

@router.get("/admin/actividades/{actividad_id}/editar")
def editar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)    
    return render(
        request, "admin/form.html", user=user, db=db,
        a=a, docentes=_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
        lista_carreras=services.carreras.get_carreras(db),
        duracion_inicial=_format_duration(a.fecha_inicio, a.fecha_fin),
        fecha_hoy=date.today().isoformat(),
    )


@router.post("/admin/actividades/{actividad_id}")
def actualizar(
    request: Request,
    actividad_id: int,
    titulo: str = Form(...),
    descripcion: str = Form(""),
    tipo: str = Form(TIPO_PRESENCIAL),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(""),
    duracion: str = Form(""),
    modo_finalizacion: str = Form("duracion"),
    lugar: str = Form(""),
    docente_id: str = Form(""),
    creditos: int = Form(1),
    cupo_max: int = Form(30),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
    carreras_asociadas: list[str] = Form([])
) -> RedirectResponse:
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    try:
        inicio, fin = _parse_dates(fecha_inicio, fecha_fin, duracion, modo_finalizacion)
    except ValueError:
        return RedirectResponse(url="/admin?err=Fechas inválidas: revisá inicio y fin.", status_code=303)
    was_published = a.estado == ESTADO_PUBLICADA
    fecha_cambio = a.fecha_inicio != inicio
    carreras_asociadas_list = services.carreras.get_carreras_desde_dropdown(carreras_asociadas, db)  
    services.actividades.update(
        db, a,
        titulo=titulo.strip(), descripcion=descripcion.strip(), tipo=tipo,
        fecha_inicio=inicio, fecha_fin=fin,
        lugar=lugar.strip(), docente_id=int(docente_id) if docente_id.isdigit() else None,
        creditos=creditos, cupo_max=cupo_max,
        carreras_asociadas=carreras_asociadas_list
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
            for enr in services.inscripcion.inscriptos(db, actividad_id):
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
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    return render(request, "admin/preview.html", user=user, db=db, a=a, cupo=services.actividades.cupo_info(db, a))


@router.post("/admin/actividades/{actividad_id}/publicar")
def publicar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    if not a.carreras_asociadas:
        return RedirectResponse(
            url="/admin?err=No se puede publicar una actividad sin carreras asociadas.",
            status_code=303,
        )
    services.actividades.update(db, a, estado=ESTADO_PUBLICADA)
    return RedirectResponse(url="/admin?msg=Actividad publicada. Ya es visible para los estudiantes.", status_code=303)


@router.post("/admin/actividades/{actividad_id}/cancelar")
def cancelar(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)) -> RedirectResponse:
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin?err=Actividad no encontrada.", status_code=303)
    services.actividades.update(db, a, estado=ESTADO_CANCELADA)
    return RedirectResponse(url="/admin?msg=Actividad cancelada.", status_code=303)
