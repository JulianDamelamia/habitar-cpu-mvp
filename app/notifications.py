"""Notification service: in-app record + optional email (replaces Redis Pub/Sub for MVP)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.email_util import send_email
from app.models.models import Notification, User


def notify(db: Session, user: User, mensaje: str, *, email_subject: str | None = None) -> None:
    """Create an in-app notification and, when a subject is given, also email the user."""
    db.add(Notification(user_id=user.id, mensaje=mensaje))
    if email_subject and user.email:
        send_email(user.email, email_subject, mensaje)


def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.leido.is_(False))
        .count()
    )
