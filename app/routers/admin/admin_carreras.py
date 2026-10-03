from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette.templating import _TemplateResponse
from starlette.responses import Response

from app import services
from app.database import get_db
from app.models import TipoCarrera, User
from app.security import REQUIERE_ADMIN, verify_password
from app.templating import redirect_to, render

router = APIRouter()

@router.get("")
def listar_carreras(
    request: Request,
    user: User = Depends(REQUIERE_ADMIN),
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


@router.get("/nueva")
def nueva_carrera(
    request: Request,
    user: User = Depends(REQUIERE_ADMIN),
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


@router.post("")
def crear_carrera(
    request: Request,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    password: str = Form(...),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if not verify_password(password, user.pw_hash):
        return redirect_to(
            request, "nueva_carrera",
            query_params={"err": "Contraseña incorrecta."},
        )

    try:
        services.carreras.add(
            db,
            nombre=nombre.strip(),
            creditos_requeridos=creditos_requeridos,
            tipo=tipo,
        )
    except ValueError as err:
        return redirect_to(
            request, "nueva_carrera",
            query_params={"err": str(err)},
        )

    return redirect_to(
        request, "listar_carreras",
        query_params={"msg": "Carrera creada correctamente."},
    )


@router.get("/{carrera_id}/editar")
def editar_carrera(
    request: Request,
    carrera_id: int,
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return redirect_to(
            request, "listar_carreras",
            query_params={"err": "Carrera no encontrada."},
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


@router.post("/{carrera_id}", name="actualizar_carrera")
def actualizar(
    request: Request,
    carrera_id: int,
    nombre: str = Form(...),
    tipo: str = Form(...),
    creditos_requeridos: int = Form(...),
    password: str = Form(...),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return redirect_to(
            request, "listar_carreras",
            query_params={"err": "Carrera no encontrada."},
        )

    if not verify_password(password, user.pw_hash):
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={"err": "Contraseña incorrecta."},
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
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={"err": str(err)},
        )

    return redirect_to(
        request, "listar_carreras",
        query_params={"msg": "Carrera actualizada."},
    )


@router.post("/{carrera_id}/verificar-eliminacion")
def verificar_eliminacion(
    request: Request,
    carrera_id: int,
    password: str = Form(...),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> Response:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return redirect_to(
            request, "listar_carreras",
            query_params={"err": "Carrera no encontrada."},
        )
    if not verify_password(password, user.pw_hash):
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={"err": "Contraseña incorrecta."},
        )
    cantidad = services.carreras.get_cantidad_inscriptos_por_carrera(db, carrera_id)
    if cantidad:
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={
                "err": (
                    "no se puede eliminar la carrera porque tiene "
                    f"{cantidad} cantidad de inscriptos. Borre los usuarios primero"
                )
            },
        )
    request.session["carrera_eliminacion_autorizada"] = carrera_id
    return redirect_to(
        request, "editar_carrera", carrera_id=carrera_id,
        query_params={"confirmar_eliminacion": "1"},
    )


@router.post("/{carrera_id}/eliminar")
def eliminar_carrera(
    request: Request,
    carrera_id: int,
    confirmar: str = Form(...),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    carrera = services.carreras.get_by_id(db, carrera_id)
    if carrera is None:
        return redirect_to(
            request, "listar_carreras",
            query_params={"err": "Carrera no encontrada."},
        )
    autorizada = request.session.get("carrera_eliminacion_autorizada") == carrera_id
    request.session.pop("carrera_eliminacion_autorizada", None)
    if confirmar != "eliminar" or not autorizada:
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={"err": "Confirmación de eliminación inválida."},
        )
    try:
        services.carreras.eliminar(db, carrera)
    except ValueError as err:
        return redirect_to(
            request, "editar_carrera", carrera_id=carrera_id,
            query_params={"err": str(err)},
        )
    return redirect_to(
        request, "listar_carreras",
        query_params={"msg": "Carrera eliminada correctamente."},
    )