"""E-08 Actividad management (coordination backoffice)."""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import _TemplateResponse

from app.database import get_db
from app.models import (
    Inscripcion,
    INSCRIPCION_ALTA,
    ESTADO_BORRADOR,
    ESTADO_CANCELADA,
    ESTADO_PUBLICADA,
    TIPO_PRESENCIAL,
    TIPO_VIRTUAL,
    User
)
from app.services.consultas_comunes import get_docentes
from app.services.notifications import notify
from app.security import REQUIERE_ADMIN
from app import services 

from app.services.parsing import formatear_duracion, parse_intervalo_tiempo
from app.templating import redirect_to, render

router = APIRouter()


@router.get("")
def panel(request: Request,carreras_asociadas: list[str] = Query([]), user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)) -> _TemplateResponse:
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


@router.get("/nueva")
def nueva(request: Request, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    return render(
        request, "admin/form.html", user=user, db=db,
        a=None, docentes=get_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
        lista_carreras=services.carreras.get_carreras(db),
        duracion_inicial="01:00",
        fecha_hoy=date.today().isoformat(),
    )


@router.post("")
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
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        inicio, fin = parse_intervalo_tiempo(fecha_inicio, fecha_fin, duracion, modo_finalizacion)
    except ValueError:
        return redirect_to(
            request, "panel",
            query_params={"err": "Fechas inválidas: revisá inicio y fin."},
        )
    carreras_asociadas_list = services.carreras.get_carreras_desde_dropdown(carreras_asociadas, db)      
    services.actividades.create(
        db,
        titulo=titulo.strip(), descripcion=descripcion.strip(), tipo=tipo,
        fecha_inicio=inicio, fecha_fin=fin, lugar=lugar.strip(),
        docente_id=int(docente_id) if docente_id.isdigit() else None,
        creditos=creditos, cupo_max=cupo_max, estado=ESTADO_BORRADOR, created_by=user.id,
        carreras_asociadas=carreras_asociadas_list,
    )
    return redirect_to(
        request, "panel",
        query_params={"msg": "Actividad creada como borrador."},
    )

@router.get("/{actividad_id}/editar")
def editar(request: Request, actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "panel",
            query_params={"err": "Actividad no encontrada."},
        )
    return render(
        request, "admin/form.html", user=user, db=db,
        a=a, docentes=get_docentes(db), tipos=[TIPO_PRESENCIAL, TIPO_VIRTUAL],
        lista_carreras=services.carreras.get_carreras(db),
        duracion_inicial=formatear_duracion(a.fecha_inicio, a.fecha_fin),
        fecha_hoy=date.today().isoformat(),
    )


@router.post("/{actividad_id}", name="actualizar_actividad")
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
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
    carreras_asociadas: list[str] = Form([])
) -> RedirectResponse:
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "panel",
            query_params={"err": "Actividad no encontrada."},
        )
    try:
        inicio, fin = parse_intervalo_tiempo(fecha_inicio, fecha_fin, duracion, modo_finalizacion)
    except ValueError:
        return redirect_to(
            request, "panel",
            query_params={"err": "Fechas inválidas: revisá inicio y fin."},
        )
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
    return redirect_to(
        request, "panel",
        query_params={"msg": "Actividad actualizada."},
    )


@router.get("/{actividad_id}/preview")
def preview(request: Request, actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "panel",
            query_params={"err": "Actividad no encontrada."},
        )
    return render(request, "admin/preview.html", user=user, db=db, a=a, cupo=services.actividades.cupo_info(db, a))


@router.post("/{actividad_id}/publicar")
def publicar(request: Request, actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "panel",
            query_params={"err": "Actividad no encontrada."},
        )
    if not a.carreras_asociadas:
        return redirect_to(
            request, "panel",
            query_params={
                "err": "No se puede publicar una actividad sin carreras asociadas."
            },
        )
    services.actividades.update(db, a, estado=ESTADO_PUBLICADA)
    return redirect_to(
        request, "panel",
        query_params={"msg": "Actividad publicada. Ya es visible para los estudiantes."},
    )


@router.post("/{actividad_id}/cancelar")
def cancelar(request: Request, actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)) -> RedirectResponse:
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "panel",
            query_params={"err": "Actividad no encontrada."},
        )
    services.actividades.update(db, a, estado=ESTADO_CANCELADA)
    return redirect_to(
        request, "panel",
        query_params={"msg": "Actividad cancelada."},
    )
