from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Actividad, Carrera, Estudiante, Inscripcion, Mensaje, ROL_ESTUDIANTE, User
from app.models.enums import INSCRIPCION_ALTA
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
    context = mensajes.coordination_compose_context(
        db,
        user,
        lectura=lectura,
        respuesta=respuesta,
        orden=orden,
    )
    return render(
        request,
        "admin/mensajes.html",
        user=user,
        db=db,
        estudiantes=context.estudiantes,
        carreras=context.carreras,
        actividades=context.actividades,
        destinatarios_disponibles={
            "estudiantes": [
                {
                    "id": f"user_{estudiante.id}",
                    "tipo": "Usuario",
                    "texto": f"{estudiante.apellido}, {estudiante.nombre} · {estudiante.email}",
                }
                for estudiante in context.estudiantes
            ],
            "carreras": [
                {"id": f"carrera_{carrera.id}", "tipo": "Carrera", "texto": carrera.nombre}
                for carrera in context.carreras
            ],
            "actividades": [
                {"id": f"act_{actividad.id}", "tipo": "Actividad", "texto": actividad.titulo}
                for actividad in context.actividades
            ],
        },
        enviados=context.enviados,
        recibidos=context.recibidos,
        consultas_no_leidas=context.consultas_no_leidas,
        respuestas_por_mensaje=context.respuestas_por_mensaje,
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
    enviar_a_todos: bool = Form(False),
    destinatarios_seleccionados: list[str] = Form([]),
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

    if enviar_a_todos:
        db.add(
            Mensaje(
                remitente_id=user.id,
                destinatario_id=None,
                asunto=asunto,
                cuerpo=cuerpo,
            )
        )
        destino_texto = "todos los estudiantes"
    else:
        if not destinatarios_seleccionados:
            return _compose_page(
                request,
                user,
                db,
                error="Seleccioná al menos un estudiante, carrera o actividad.",
            )

        recipient_ids: set[int] = set()
        try:
            for selection in destinatarios_seleccionados:
                kind, raw_id = selection.split("_", 1)
                selected_id = int(raw_id)
                if kind == "user":
                    student_id = (
                        db.query(User.id)
                        .join(Estudiante, Estudiante.user_id == User.id)
                        .filter(User.id == selected_id, User.rol == ROL_ESTUDIANTE)
                        .scalar()
                    )
                    if student_id is None:
                        raise ValueError
                    recipient_ids.add(student_id)
                elif kind == "carrera":
                    carrera = db.get(Carrera, selected_id)
                    if carrera is None:
                        raise ValueError
                    career_students = (
                        db.query(User.id)
                        .join(Estudiante, Estudiante.user_id == User.id)
                        .filter(
                            User.rol == ROL_ESTUDIANTE,
                            Estudiante.carrera_id == selected_id,
                        )
                        .all()
                    )
                    recipient_ids.update(row[0] for row in career_students)
                elif kind == "act":
                    actividad = db.get(Actividad, selected_id)
                    if actividad is None:
                        raise ValueError
                    activity_students = (
                        db.query(Inscripcion.user_id)
                        .join(User, User.id == Inscripcion.user_id)
                        .join(Estudiante, Estudiante.user_id == User.id)
                        .filter(
                            Inscripcion.actividad_id == selected_id,
                            Inscripcion.estado == INSCRIPCION_ALTA,
                            User.rol == ROL_ESTUDIANTE,
                        )
                        .all()
                    )
                    recipient_ids.update(row[0] for row in activity_students)
                else:
                    raise ValueError
        except ValueError:
            raise HTTPException(status_code=422, detail="Destinatario inválido.") from None

        if not recipient_ids:
            return _compose_page(
                request,
                user,
                db,
                error="La selección no tiene estudiantes destinatarios.",
            )

        db.add_all(
            Mensaje(
                remitente_id=user.id,
                destinatario_id=recipient_id,
                asunto=asunto,
                cuerpo=cuerpo,
            )
            for recipient_id in sorted(recipient_ids)
        )
        destino_texto = f"{len(recipient_ids)} estudiante(s) seleccionados"

    db.commit()
    return redirect_to(
        request,
        "admin_mensajes",
        query_params={
            "msg": f"Mensaje enviado a {destino_texto}."
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
