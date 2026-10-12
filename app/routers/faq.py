"""E-04 (US-15) FAQ: public read + coordination management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Faq, Mensaje, ROL_COORDINACION, User
from app.security import current_user_required, requiere_roles
from app.templating import redirect_to, render

router = APIRouter()
admin_faq_router = APIRouter()


@router.get("/faq")
def faq_list(request: Request, user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.orden, Faq.id).all()
    return render(request, "shared/faq.html", user=user, db=db, items=items)


@admin_faq_router.get("")
def faq_admin(request: Request, user: User = Depends(requiere_roles("coordinacion")), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.orden, Faq.id).all()
    return render(request, "admin/faq.html", user=user, db=db, items=items)


@admin_faq_router.post("")
def faq_add(
    request: Request,
    pregunta: str = Form(...),
    respuesta: str = Form(...),
    orden: int = Form(0),
    tags: str = Form(""),
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    db.add(
        Faq(
            pregunta=pregunta.strip(),
            respuesta=respuesta.strip(),
            orden=orden,
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
    orden: int = Form(0),
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
    item.pregunta = pregunta
    item.respuesta = respuesta
    item.orden = orden
    item.tags = ", ".join(dict.fromkeys(tag.strip() for tag in tags.split(",") if tag.strip()))
    db.commit()
    return redirect_to(request, "faq_admin", query_params={"msg": "Pregunta actualizada."})


@router.post("/faq/contacto", name="faq_contacto")
def faq_contacto(
    request: Request,
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    busqueda: str = Form(...),
    user: User = Depends(requiere_roles("estudiante")),
    db: Session = Depends(get_db),
):
    asunto = asunto.strip()
    cuerpo = cuerpo.strip()
    busqueda = busqueda.strip()
    if not busqueda or not asunto or len(asunto) > 200 or not cuerpo:
        return redirect_to(
            request, "faq_list",
            query_params={"err": "Buscá primero en las preguntas frecuentes e ingresá asunto y mensaje."},
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
            asunto=asunto,
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
