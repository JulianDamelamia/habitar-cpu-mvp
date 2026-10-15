"""E-04 (US-15) FAQ: public read + coordination management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Faq, FaqCategoria, Mensaje, ROL_COORDINACION, User
from app.security import current_user_required, requiere_roles
from app.templating import redirect_to, render

router = APIRouter()
admin_faq_router = APIRouter()


@router.get("/faq")
def faq_list(request: Request, user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.id).all()
    categories = db.query(FaqCategoria).order_by(FaqCategoria.id).all()
    return render(request, "shared/faq.html", user=user, db=db, items=items, categories=categories)


@admin_faq_router.get("")
def faq_admin(request: Request, user: User = Depends(requiere_roles("coordinacion")), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.id).all()
    categories = db.query(FaqCategoria).order_by(FaqCategoria.id).all()
    return render(request, "admin/faq.html", user=user, db=db, items=items, categories=categories)


@admin_faq_router.post("")
def faq_add(
    request: Request,
    pregunta: str = Form(...),
    respuesta: str = Form(...),
    categoria_id: int = Form(...),
    tags: str = Form(""),
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    categoria = db.get(FaqCategoria, categoria_id)
    if categoria is None:
        return redirect_to(request, "faq_admin", query_params={"err": "Seleccioná una categoría válida."})
    db.add(
        Faq(
            pregunta=pregunta.strip(),
            respuesta=respuesta.strip(),
            categoria_id=categoria.id,
            tags=", ".join(dict.fromkeys(tag.strip() for tag in tags.split(",") if tag.strip())),
        )
    )
    db.commit()
    return redirect_to(
        request, "faq_admin",
        query_params={"msg": "Pregunta agregada."},
    )


@admin_faq_router.post("/{faq_id}/update", name="faq_update")
def faq_update(
    request: Request,
    faq_id: int,
    pregunta: str = Form(...),
    respuesta: str = Form(...),
    categoria_id: int = Form(...),
    tags: str = Form(""),
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    item = db.get(Faq, faq_id)
    if item is None:
        return redirect_to(
            request, "faq_admin",
            query_params={"err": "Pregunta frecuente no encontrada."},
        )

    pregunta = pregunta.strip()
    respuesta = respuesta.strip()
    if not pregunta or not respuesta:
        return redirect_to(
            request, "faq_admin",
            query_params={"err": "Pregunta y respuesta son obligatorias."},
        )
    categoria = db.get(FaqCategoria, categoria_id)
    if categoria is None:
        return redirect_to(request, "faq_admin", query_params={"err": "Seleccioná una categoría válida."})
    item.pregunta = pregunta
    item.respuesta = respuesta
    item.categoria_id = categoria.id
    item.tags = ", ".join(dict.fromkeys(tag.strip() for tag in tags.split(",") if tag.strip()))
    db.commit()
    return redirect_to(request, "faq_admin", query_params={"msg": "Pregunta actualizada."})


@admin_faq_router.post("/categorias", name="faq_categoria_add")
def faq_categoria_add(
    request: Request,
    nombre: str = Form(...),
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    nombre = nombre.strip()
    if not nombre or len(nombre) > 100:
        return redirect_to(request, "faq_admin", query_params={"err": "La categoría debe tener entre 1 y 100 caracteres."})
    existing = db.query(FaqCategoria).filter(FaqCategoria.nombre == nombre).first()
    if existing:
        return redirect_to(request, "faq_admin", query_params={"err": "Esa categoría ya existe."})
    db.add(FaqCategoria(nombre=nombre))
    db.commit()
    return redirect_to(request, "faq_admin", query_params={"msg": "Categoría agregada."})


@router.post("/faq/contacto", name="faq_contacto")
def faq_contacto(
    request: Request,
    categoria_id: int = Form(...),
    cuerpo: str = Form(...),
    busqueda: str = Form(...),
    user: User = Depends(requiere_roles("estudiante")),
    db: Session = Depends(get_db),
):
    cuerpo = cuerpo.strip()
    busqueda = busqueda.strip()
    categoria = db.get(FaqCategoria, categoria_id)
    if not busqueda or categoria is None or not cuerpo:
        return redirect_to(
            request, "faq_list",
            query_params={"err": "Buscá primero en las preguntas frecuentes, elegí un tema e ingresá un mensaje."},
        )

    coordinadores = (
        db.query(User)
        .filter(User.rol == ROL_COORDINACION)
        .order_by(User.id)
        .all()
    )
    if not coordinadores:
        return redirect_to(
            request, "faq_list",
            query_params={"err": "No hay cuentas de coordinación disponibles para recibir mensajes."},
        )

    db.add_all(
        Mensaje(
            remitente_id=user.id,
            destinatario_id=coordinador.id,
            asunto=categoria.nombre,
            cuerpo=cuerpo,
        )
        for coordinador in coordinadores
    )
    db.commit()
    return redirect_to(
        request, "faq_list",
        query_params={"msg": "Tu mensaje fue enviado a coordinación."},
    )


@admin_faq_router.post("/{faq_id}/delete")
def faq_delete(
    request: Request,
    faq_id: int,
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    item = db.get(Faq, faq_id)
    if item:
        db.delete(item)
        db.commit()
    return redirect_to(
        request, "faq_admin",
        query_params={"msg": "Pregunta eliminada."},
    )
