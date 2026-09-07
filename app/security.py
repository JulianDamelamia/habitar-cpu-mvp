"""Authentication: password hashing, session cookies, rol guards."""
from __future__ import annotations

import bcrypt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


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


def current_user_required(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if user is None:
        raise NotAuthenticated()
    return user


def requiere_roles(*roles: str):
    def dependency(user: User = Depends(current_user_required)) -> User:
        if user.rol not in roles:
            raise NotAuthorized()
        return user

    return dependency
