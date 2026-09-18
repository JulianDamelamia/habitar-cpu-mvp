from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import _TemplateResponse

from app import services
from app.database import get_db
from app.models import Carrera, TipoCarrera, User
from app.security import requiere_roles
from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")


@router.get("/admin/carreras")
def listar_carreras(
    request: Request,
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> _TemplateResponse:
    carreras_list = services.carreras.get_carreras(db)
    return render(
        request,
        "admin/carreras/index.html",
        user=user,
        db=db,
        carreras_list=carreras_list,
    )


@router.get("/admin/carreras/nueva")
def nueva_carrera(
    request: Request,
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> _TemplateResponse:
    return render(
        request,
        "admin/carreras/form.html",
        user=user,
        db=db,
        carrera=None,
        tipos=[t.nombre for t in TipoCarrera],
    )


@router.post("/admin/carreras")
def crear_carrera(
    request: Request,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        services.carreras.add(
            db,
            nombre=nombre.strip(),
            creditos_requeridos=creditos_requeridos,
            tipo=tipo,
        )
    except ValueError as err:
        return RedirectResponse(
            url=f"/admin/carreras/nueva?err={err}",
            status_code=303,
        )

    return RedirectResponse(
        url="/admin/carreras?msg=Carrera creada correctamente.",
        status_code=303,
    )


@router.get("/admin/carreras/{carrera_id}/editar")
def editar_carrera(
    request: Request,
    carrera_id: int,
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse | _TemplateResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return RedirectResponse(
            url="/admin/carreras?err=Carrera no encontrada.",
            status_code=303,
        )
    return render(
        request,
        "admin/carreras/form.html",
        user=user,
        db=db,
        carrera=carrera,
        tipos=[t.value for t in TipoCarrera],
    )


@router.post("/admin/carreras/{carrera_id}")
def actualizar(
    request: Request,
    carrera_id: int,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return RedirectResponse(
            url="/admin/carreras?err=Carrera no encontrada.",
            status_code=303,
        )

    try:
        services.carreras.update(
            db,
            carrera,
            nombre=nombre,
            creditos_requeridos=creditos_requeridos,
            tipo=tipo,
        )
    except ValueError as err:
        return RedirectResponse(
            url=f"/admin/carreras/{carrera_id}/editar?err={err}",
            status_code=303,
        )

    return RedirectResponse(
        url="/admin/carreras?msg=Carrera actualizada.",
        status_code=303,
    )