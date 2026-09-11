"""E-04 (US-15) FAQ: public read + coordination management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Faq, User
from app.security import current_user_required, requiere_roles
from app.templating import render

router = APIRouter()


@router.get("/faq")
def faq_list(request: Request, user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.orden, Faq.id).all()
    return render(request, "shared/faq.html", user=user, db=db, items=items)


@router.get("/admin/faq")
def faq_admin(request: Request, user: User = Depends(requiere_roles("coordinacion")), db: Session = Depends(get_db)):
    items = db.query(Faq).order_by(Faq.orden, Faq.id).all()
    return render(request, "admin/faq.html", user=user, db=db, items=items)


@router.post("/admin/faq")
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
    return RedirectResponse(url="/admin/faq?msg=Pregunta agregada.", status_code=303)


@router.post("/admin/faq/{faq_id}/delete")
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
    return RedirectResponse(url="/admin/faq?msg=Pregunta eliminada.", status_code=303)
