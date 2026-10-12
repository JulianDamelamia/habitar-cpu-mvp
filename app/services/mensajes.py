from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

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


def coordination_inbox(
    db: Session,
    user: User,
    *,
    lectura: str = "todas",
    respuesta: str = "todas",
    orden: str = "desc",
) -> tuple[list[Mensaje], int, dict[int, list[Mensaje]]]:
    reply = aliased(Mensaje)
    query = (
        db.query(Mensaje)
        .join(User, User.id == Mensaje.remitente_id)
        .filter(
            Mensaje.destinatario_id == user.id,
            Mensaje.reply_to_id.is_(None),
            User.rol == ROL_ESTUDIANTE,
        )
    )
    unread_count = query.filter(Mensaje.leido.is_(False)).count()
    if lectura == "no_leidos":
        query = query.filter(Mensaje.leido.is_(False))
    elif lectura == "leidos":
        query = query.filter(Mensaje.leido.is_(True))
    if respuesta == "no_respondidos":
        query = query.filter(
            ~db.query(reply.id).filter(reply.reply_to_id == Mensaje.id).exists()
        )
    elif respuesta == "respondidos":
        query = query.filter(
            db.query(reply.id).filter(reply.reply_to_id == Mensaje.id).exists()
        )

    date_order = Mensaje.created_at.asc() if orden == "asc" else Mensaje.created_at.desc()
    id_order = Mensaje.id.asc() if orden == "asc" else Mensaje.id.desc()
    messages = query.order_by(date_order, id_order).limit(100).all()
    message_ids = [message.id for message in messages]
    replies = (
        db.query(Mensaje)
        .filter(Mensaje.reply_to_id.in_(message_ids))
        .order_by(Mensaje.created_at, Mensaje.id)
        .all()
        if message_ids
        else []
    )
    replies_by_message: dict[int, list[Mensaje]] = {}
    for message in replies:
        replies_by_message.setdefault(message.reply_to_id, []).append(message)
    return messages, unread_count, replies_by_message
