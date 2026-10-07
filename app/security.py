"""Authentication: password hashing, session cookies, rol guards."""
from __future__ import annotations

import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ROL_COORDINACION
from app.models.enums import ROL_ESTUDIANTE


# ---- Passwords ---------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---- Session helpers ---------------------------------------------------------
def login_user(request: Request, user: User) -> None:
    request.session["user_id"] = user.id


def logout_user(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


# ---- Auth control flow -------------------------------------------------------
class NotAuthenticated(Exception):
    """Raised when a protected route has no logged-in user -> redirect to /login."""


class NotAuthorized(Exception):
    """Raised when the user lacks the required rol -> 403."""


class CarreraPendienteException(Exception):
    pass


def current_user_required_base(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise NotAuthenticated()
    return user


# Require students to complete onboarding before using protected routes.
def current_user_required(request: Request, db: Session = Depends(get_db)) -> User:
    user = current_user_required_base(request, db)

    if user.rol == ROL_ESTUDIANTE and (
        user.carrera_id is None or user.debe_cambiar_pw
    ):
        path_seleccion = request.url_for("seleccionar_carrera_form").path
        path_logout = request.url_for("logout").path

        if request.url.path not in [path_seleccion, path_logout]:
            raise CarreraPendienteException()

    return user


def requiere_roles(*roles: str):
    def dependency(user: User = Depends(current_user_required)) -> User:
        if user.rol not in roles:
            raise NotAuthorized()
        return user

    return dependency

REQUIERE_ADMIN = requiere_roles(ROL_COORDINACION)