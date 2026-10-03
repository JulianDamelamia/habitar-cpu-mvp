"""E-04 (US-15) FAQ: public read + coordination management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Faq, User
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
    user: User = Depends(requiere_roles("coordinacion")),
    db: Session = Depends(get_db),
):
    db.add(Faq(pregunta=pregunta.strip(), respuesta=respuesta.strip(), orden=orden))
    db.commit()
    return redirect_to(
        request, "faq_admin",
        query_params={"msg": "Pregunta agregada."},
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
