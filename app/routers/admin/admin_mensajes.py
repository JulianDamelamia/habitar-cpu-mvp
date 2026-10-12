from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Estudiante, Mensaje, ROL_ESTUDIANTE, User
from app.security import REQUIERE_ADMIN
from app.services import mensajes
from app.templating import redirect_to, render

router = APIRouter()


def _compose_page(
    request: Request,
    user: User,
    db: Session,
    *,
    error: str | None = None,
    lectura: str = "todas",
    respuesta: str = "todas",
    orden: str = "desc",
):
    estudiantes = (
        db.query(User)
        .join(Estudiante, Estudiante.user_id == User.id)
        .filter(User.rol == ROL_ESTUDIANTE)
        .order_by(User.apellido, User.nombre)
        .all()
    )
    enviados = (
        db.query(Mensaje)
        .filter(Mensaje.remitente_id == user.id)
        .order_by(Mensaje.created_at.desc(), Mensaje.id.desc())
        .limit(50)
        .all()
    )
    recibidos, consultas_no_leidas, respuestas_por_mensaje = mensajes.coordination_inbox(
        db, user, lectura=lectura, respuesta=respuesta, orden=orden
    )
    return render(
        request,
        "admin/mensajes.html",
        user=user,
        db=db,
        estudiantes=estudiantes,
        enviados=enviados,
        recibidos=recibidos,
        consultas_no_leidas=consultas_no_leidas,
        respuestas_por_mensaje=respuestas_por_mensaje,
        lectura=lectura,
        respuesta=respuesta,
        orden=orden,
        form_error=error,
        filter_endpoint="admin_mensajes",
        reply_return_to="admin_mensajes",
    )


@router.get("", name="admin_mensajes")
def admin_mensajes(
    request: Request,
    lectura: str = "todas",
    respuesta: str = "todas",
    orden: str = "desc",
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    if lectura not in {"todas", "no_leidos", "leidos"}:
        raise HTTPException(status_code=422, detail="Filtro de lectura inválido.")
    if respuesta not in {"todas", "no_respondidos", "respondidos"}:
        raise HTTPException(status_code=422, detail="Filtro de respuesta inválido.")
    if orden not in {"asc", "desc"}:
        raise HTTPException(status_code=422, detail="Orden de fecha inválido.")
    return _compose_page(
        request, user, db, lectura=lectura, respuesta=respuesta, orden=orden
    )


@router.post("", name="enviar_mensaje")
def enviar_mensaje(
    request: Request,
    asunto: str = Form(...),
    cuerpo: str = Form(...),
    destinatario_id: str = Form(""),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    asunto = asunto.strip()
    cuerpo = cuerpo.strip()
    if not asunto or len(asunto) > 200 or not cuerpo:
        return _compose_page(
            request, user, db,
            error="Asunto obligatorio (máximo 200 caracteres) y mensaje obligatorio.",
        )

    destinatario = None
    if destinatario_id:
        try:
            recipient_id = int(destinatario_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="Destinatario inválido.") from None
        destinatario = (
            db.query(User)
            .join(Estudiante, Estudiante.user_id == User.id)
            .filter(User.id == recipient_id, User.rol == ROL_ESTUDIANTE)
            .one_or_none()
        )
        if destinatario is None:
            raise HTTPException(status_code=404, detail="Estudiante destinatario no encontrado.")

    db.add(
        Mensaje(
            remitente_id=user.id,
            destinatario_id=destinatario.id if destinatario else None,
            asunto=asunto,
            cuerpo=cuerpo,
        )
    )
    db.commit()
    return redirect_to(
        request,
        "admin_mensajes",
        query_params={
            "msg": (
                f"Mensaje enviado a {destinatario.nombre_completo}."
                if destinatario
                else "Mensaje enviado a todos los estudiantes."
            )
        },
    )


@router.post("/{mensaje_id}/responder", name="responder_mensaje")
def responder_mensaje(
    request: Request,
    mensaje_id: int,
    cuerpo: str = Form(...),
    return_to: str = Form("admin_mensajes"),
    lectura: str = Form("todas"),
    respuesta: str = Form("todas"),
    orden: str = Form("desc"),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    original = db.get(Mensaje, mensaje_id)
    if (
        original is None
        or original.destinatario_id != user.id
        or original.reply_to_id is not None
        or original.remitente.rol != ROL_ESTUDIANTE
    ):
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")
    if return_to not in {"admin_mensajes", "notificaciones"}:
        raise HTTPException(status_code=422, detail="Destino de respuesta inválido.")
    if (
        lectura not in {"todas", "no_leidos", "leidos"}
        or respuesta not in {"todas", "no_respondidos", "respondidos"}
        or orden not in {"asc", "desc"}
    ):
        raise HTTPException(status_code=422, detail="Filtro de bandeja inválido.")

    cuerpo = cuerpo.strip()
    if not cuerpo:
        error_params = {
            "err": "La respuesta no puede estar vacía.",
            "lectura": lectura,
            "respuesta": respuesta,
            "orden": orden,
        }
        if return_to == "notificaciones":
            error_params["tab"] = "mensajes"
        return redirect_to(
            request, return_to, query_params=error_params,
        )

    db.add(
        Mensaje(
            remitente_id=user.id,
            destinatario_id=original.remitente_id,
            reply_to_id=original.id,
            asunto=f"Re: {original.asunto}"[:200],
            cuerpo=cuerpo,
        )
    )
    original.leido = True
    db.commit()
    query_params = {
        "msg": "Respuesta enviada al estudiante.",
        "lectura": lectura,
        "respuesta": respuesta,
        "orden": orden,
    }
    if return_to == "notificaciones":
        query_params["tab"] = "mensajes"
    return redirect_to(request, return_to, query_params=query_params)
