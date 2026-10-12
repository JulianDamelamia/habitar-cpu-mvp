from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Mensaje, Notification, User
from app.security import current_user_required
from app.services import mensajes
from app.templating import render

router = APIRouter()


@router.get("/notificaciones", name="notificaciones")
def notificaciones_page(
    request: Request,
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    avisos = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
        .all()
    )
    notificaciones_no_leidas = (
        db.query(Notification.id)
        .filter(
            Notification.user_id == user.id,
            Notification.leido.is_(False),
        )
        .count()
    )
    mensajes_usuario = mensajes.inbox(db, user)
    mensajes_no_leidos = mensajes.unread_count(db, user)
    lecturas = {
        mensaje.id: mensajes.is_read(db, mensaje, user.id)
        for mensaje in mensajes_usuario
    }

    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.leido.is_(False)
    ).update({Notification.leido: True}, synchronize_session=False)
    db.commit()

    return render(
        request,
        "shared/notificaciones.html",
        user=user,
        db=db,
        items=avisos,
        mensajes=mensajes_usuario,
        lecturas=lecturas,
        notificaciones_no_leidas=notificaciones_no_leidas,
        mensajes_no_leidos=mensajes_no_leidos,
    )


@router.post("/notificaciones/mensajes/{mensaje_id}/leer", name="leer_mensaje")
def leer_mensaje(
    mensaje_id: int,
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    mensaje = db.get(Mensaje, mensaje_id)
    if mensaje is None:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")
    visible = mensaje.destinatario_id == user.id or (
        mensaje.destinatario_id is None and user.rol == "estudiante"
    )
    if not visible:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.")

    mensajes.mark_read(db, mensaje, user.id)
    db.commit()
    return JSONResponse({"id": mensaje.id, "leido": True})
