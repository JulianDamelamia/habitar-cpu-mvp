from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import _TemplateResponse
from starlette.responses import Response

from app import services
from app.database import get_db
from app.models import Carrera, TipoCarrera, User
from app.security import requiere_roles, verify_password
from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")


@router.get("/admin/carreras")
def listar_carreras(
    request: Request,
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> _TemplateResponse:
    tipo = request.query_params.get("tipo", "")
    nombre = request.query_params.get("nombre", "").strip()
    orden = request.query_params.get("orden", "nombre")
    direccion = request.query_params.get("direccion", "asc")
    if orden not in {"nombre", "inscriptos", "creditos"}:
        orden = "nombre"
    if direccion not in {"asc", "desc"}:
        direccion = "asc"

    carreras = services.carreras.get_carreras(db)

    if tipo:
        carreras = [carrera for carrera in carreras if carrera.tipo.nombre == tipo]
    if nombre:
        nombre_normalizado = nombre.casefold()
        carreras = [
            carrera
            for carrera in carreras
            if nombre_normalizado in carrera.nombre.casefold()
        ]

    inscriptos_por_carrera = {
        carrera.id: services.carreras.get_cantidad_inscriptos_por_carrera(
            db, carrera.id
        )
        for carrera in carreras
    }
    total_inscriptos = sum(inscriptos_por_carrera.values())
    total_ingenieria = sum(
        carrera.tipo.nombre == "Ingeniería" for carrera in carreras
    )
    total_licenciatura = sum(
        carrera.tipo.nombre == "Licenciatura" for carrera in carreras
    )

    if orden == "nombre":
        clave_orden = lambda carrera: (
            f"{carrera.tipo.nombre} {carrera.nombre}".casefold()
        )
    elif orden == "inscriptos":
        clave_orden = lambda carrera: inscriptos_por_carrera.get(carrera.id, 0)
    else:
        clave_orden = lambda carrera: carrera.creditos_requeridos
    carreras.sort(key=clave_orden, reverse=direccion == "desc")

    def url_orden(nuevo_orden: str) -> str:
        nueva_direccion = (
            "desc"
            if orden == nuevo_orden and direccion == "asc"
            else "asc"
        )
        parametros_orden = {
            "orden": nuevo_orden,
            "direccion": nueva_direccion,
        }
        if tipo:
            parametros_orden["tipo"] = tipo
        if nombre:
            parametros_orden["nombre"] = nombre
        return str(
            request.url.include_query_params(**parametros_orden)
        )

    return render(
        request,
        "admin/carreras/index.html",
        user=user,
        db=db,
        carreras=carreras,
        inscriptos_por_carrera=inscriptos_por_carrera,
        total_inscriptos=total_inscriptos,
        total_ingenieria=total_ingenieria,
        total_licenciatura=total_licenciatura,
        tipo_seleccionado=tipo,
        nombre_buscado=nombre,
        orden_actual=orden,
        direccion_actual=direccion,
        urls_orden={
            "nombre": url_orden("nombre"),
            "inscriptos": url_orden("inscriptos"),
            "creditos": url_orden("creditos"),
        },
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
        tipos=[
            tipo.nombre
            for tipo in db.query(TipoCarrera).order_by(TipoCarrera.nombre).all()
        ],
    )


@router.post("/admin/carreras")
def crear_carrera(
    request: Request,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    password: str = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not verify_password(password, user.pw_hash):
        return RedirectResponse(
            url="/admin/carreras/nueva?err=Contraseña incorrecta.",
            status_code=303,
        )

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
) -> Response:
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
        tipos=[
            tipo.nombre
            for tipo in db.query(TipoCarrera).order_by(TipoCarrera.nombre).all()
        ],
    )


@router.post("/admin/carreras/{carrera_id}")
def actualizar(
    request: Request,
    carrera_id: int,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    password: str = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return RedirectResponse(
            url="/admin/carreras?err=Carrera no encontrada.",
            status_code=303,
        )

    if not verify_password(password, user.pw_hash):
        return RedirectResponse(
            url=f"/admin/carreras/{carrera_id}/editar?err=Contraseña incorrecta.",
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


@router.post("/admin/carreras/{carrera_id}/verificar-eliminacion")
def verificar_eliminacion(
    request: Request,
    carrera_id: int,
    password: str = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return RedirectResponse(
            url="/admin/carreras?err=Carrera no encontrada.", status_code=303
        )
    if not verify_password(password, user.pw_hash):
        return RedirectResponse(
            url=f"/admin/carreras/{carrera_id}/editar?err=Contraseña incorrecta.",
            status_code=303,
        )
    cantidad = services.carreras.get_cantidad_inscriptos_por_carrera(db, carrera_id)
    if cantidad:
        return RedirectResponse(
            url=(
                f"/admin/carreras/{carrera_id}/editar?err=no se puede eliminar "
                f"la carrera porque tiene {cantidad} cantidad de inscriptos. "
                "Borre los usuarios primero"
            ),
            status_code=303,
        )
    request.session["carrera_eliminacion_autorizada"] = carrera_id
    return RedirectResponse(
        url=f"/admin/carreras/{carrera_id}/editar?confirmar_eliminacion=1",
        status_code=303,
    )


@router.post("/admin/carreras/{carrera_id}/eliminar")
def eliminar_carrera(
    request: Request,
    carrera_id: int,
    confirmar: str = Form(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return RedirectResponse(
            url="/admin/carreras?err=Carrera no encontrada.", status_code=303
        )
    autorizada = request.session.get("carrera_eliminacion_autorizada") == carrera_id
    request.session.pop("carrera_eliminacion_autorizada", None)
    if confirmar != "eliminar" or not autorizada:
        return RedirectResponse(
            url=f"/admin/carreras/{carrera_id}/editar?err=Confirmación de eliminación inválida.",
            status_code=303,
        )
    try:
        services.carreras.eliminar(db, carrera)
    except ValueError as err:
        return RedirectResponse(
            url=f"/admin/carreras/{carrera_id}/editar?err={err}", status_code=303
        )
    return RedirectResponse(
        url="/admin/carreras?msg=Carrera eliminada correctamente.", status_code=303
    )