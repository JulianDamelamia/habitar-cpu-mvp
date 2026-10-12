from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models import Mensaje, MensajeLectura, ROL_ESTUDIANTE, User


def inbox(db: Session, user: User) -> list[Mensaje]:
    query = db.query(Mensaje).filter(
        or_(
            Mensaje.destinatario_id == user.id,
            and_(Mensaje.destinatario_id.is_(None), user.rol == ROL_ESTUDIANTE),
        )
    )
    return query.order_by(Mensaje.created_at.desc(), Mensaje.id.desc()).limit(100).all()


def is_read(db: Session, mensaje: Mensaje, user_id: int) -> bool:
    if mensaje.destinatario_id is not None:
        return mensaje.leido
    return (
        db.query(MensajeLectura.mensaje_id)
        .filter(
            MensajeLectura.mensaje_id == mensaje.id,
            MensajeLectura.user_id == user_id,
            MensajeLectura.leido.is_(True),
        )
        .first()
        is not None
    )


def mark_read(db: Session, mensaje: Mensaje, user_id: int) -> None:
    if mensaje.destinatario_id is not None:
        mensaje.leido = True
        return
    receipt = db.get(MensajeLectura, (mensaje.id, user_id))
    if receipt is None:
        db.add(MensajeLectura(mensaje_id=mensaje.id, user_id=user_id))
    else:
        receipt.leido = True


def unread_count(db: Session, user: User) -> int:
    direct_unread = (
        db.query(Mensaje.id)
        .filter(
            Mensaje.destinatario_id == user.id,
            Mensaje.leido.is_(False),
        )
        .count()
    )
    if user.rol != ROL_ESTUDIANTE:
        return direct_unread
    broadcast_unread = (
        db.query(Mensaje.id)
        .filter(
            Mensaje.destinatario_id.is_(None),
            ~Mensaje.lecturas.any(
                and_(
                    MensajeLectura.user_id == user.id,
                    MensajeLectura.leido.is_(True),
                )
            ),
        )
        .count()
    )
    return direct_unread + broadcast_unread
