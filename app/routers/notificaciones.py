from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Mensaje, Notification, ROL_COORDINACION, User
from app.security import current_user_required
from app.services import mensajes
from app.templating import render

router = APIRouter()


@router.get("/notificaciones", name="notificaciones")
def notificaciones_page(
    request: Request,
    lectura: str = "todas",
    respuesta: str = "todas",
    orden: str = "desc",
    tab: str = "notificaciones",
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    es_coordinacion = user.rol == ROL_COORDINACION
    if es_coordinacion:
        if lectura not in {"todas", "no_leidos", "leidos"}:
            raise HTTPException(status_code=422, detail="Filtro de lectura inválido.")
        if respuesta not in {"todas", "no_respondidos", "respondidos"}:
            raise HTTPException(status_code=422, detail="Filtro de respuesta inválido.")
        if orden not in {"asc", "desc"}:
            raise HTTPException(status_code=422, detail="Orden de fecha inválido.")
        if tab not in {"notificaciones", "mensajes"}:
            raise HTTPException(status_code=422, detail="Pestaña inválida.")
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
    admin_inbox = {}
    if es_coordinacion:
        (
            mensajes_usuario,
            consultas_no_leidas,
            respuestas_por_mensaje,
        ) = mensajes.coordination_inbox(
            db, user, lectura=lectura, respuesta=respuesta, orden=orden
        )
        admin_inbox = {
            "recibidos": mensajes_usuario,
            "consultas_no_leidas": consultas_no_leidas,
            "respuestas_por_mensaje": respuestas_por_mensaje,
            "lectura": lectura,
            "respuesta": respuesta,
            "orden": orden,
            "tab": tab,
        }
        lecturas = {message.id: message.leido for message in mensajes_usuario}
    else:
        mensajes_usuario = mensajes.inbox(db, user)
        lecturas = {
            message.id: mensajes.is_read(db, message, user.id)
            for message in mensajes_usuario
        }
    mensajes_no_leidos = mensajes.unread_count(db, user)

    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.leido.is_(False)
    ).update({Notification.leido: True}, synchronize_session=False)
    db.commit()

    if es_coordinacion:
        template = "admin/notificaciones.html"
    else:
        template = "shared/notificaciones.html"

    return render(
        request,
        template,
        user=user,
        db=db,
        items=avisos,
        mensajes=mensajes_usuario,
        lecturas=lecturas,
        notificaciones_no_leidas=notificaciones_no_leidas,
        mensajes_no_leidos=mensajes_no_leidos,
        **admin_inbox,
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
