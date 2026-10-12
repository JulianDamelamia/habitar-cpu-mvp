from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Estudiante, Mensaje, ROL_ESTUDIANTE, User
from app.security import REQUIERE_ADMIN
from app.templating import redirect_to, render

router = APIRouter()


def _compose_page(request: Request, user: User, db: Session, *, error: str | None = None):
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
    return render(
        request,
        "admin/mensajes.html",
        user=user,
        db=db,
        estudiantes=estudiantes,
        enviados=enviados,
        form_error=error,
    )


@router.get("", name="admin_mensajes")
def admin_mensajes(
    request: Request,
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    return _compose_page(request, user, db)


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
