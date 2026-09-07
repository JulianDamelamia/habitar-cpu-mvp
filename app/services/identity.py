"""Identity / SIU-mock service. Single swap point for real SIU Guaraní integration."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import ROL_ESTUDIANTE, User, ValidLegajo
from app.security import hash_password, verify_password


class SignupError(Exception):
    pass


def legajo_is_valid(db: Session, legajo: str) -> bool:
    """SIU Guaraní simulator lookup."""
    return db.get(ValidLegajo, legajo.strip()) is not None


def email_taken(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email.lower().strip()).first() is not None


def create_student(
    db: Session,
    *,
    legajo: str,
    email: str,
    password: str,
    nombre: str,
    apellido: str,
    dni: str | None,
    carrera: str | None,
) -> User:
    legajo = legajo.strip()
    email = email.lower().strip()
    if not legajo_is_valid(db, legajo):
        raise SignupError("El legajo no figura en el padrón UNSAM (SIU Guaraní).")
    if email_taken(db, email):
        raise SignupError("Ya existe una cuenta con ese email.")
    user = User(
        legajo=legajo,
        email=email,
        pw_hash=hash_password(password),
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        dni=(dni or "").strip() or None,
        carrera=(carrera or "").strip() or None,
        rol=ROL_ESTUDIANTE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.lower().strip()).first()
    if user and verify_password(password, user.pw_hash):
        return user
    return None
