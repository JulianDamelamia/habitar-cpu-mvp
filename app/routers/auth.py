"""E-01 Authentication & profile."""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import PasswordReset, User
from app.models.carrera import Carrera
from app.models.enums import ROL_ESTUDIANTE
from app.security import (
    current_user_required,
    current_user_required_base,
    hash_password,
    login_user,
    logout_user,
)
from app import services
from app.templating import redirect_to, render

router = APIRouter()
logger = logging.getLogger("habitar.auth")

PASSWORD_RESET_TTL = timedelta(minutes=15)
PASSWORD_RESET_COOLDOWN = timedelta(seconds=60)
PASSWORD_RESET_MAX_ATTEMPTS = 5


def _password_reset_digest(email: str, code: str) -> str:
    value = f"{email}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), value, hashlib.sha256).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _render_password_reset(
    request: Request,
    *,
    email: str = "",
    message: str | None = None,
    error: str | None = None,
    show_code_form: bool = False,
):
    return render(
        request,
        "auth/password_reset.html",
        email=email,
        message=message,
        error=error,
        show_code_form=show_code_form,
    )


@router.get("/login")
def login_form(request: Request):
    return render(request, "auth/login.html")


@router.get("/recuperar-contrasena")
def password_reset_form(request: Request):
    return _render_password_reset(request)


@router.post("/recuperar-contrasena")
def password_reset_submit(
    request: Request,
    action: str = Form(...),
    email: str = Form(...),
    code: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
    db: Session = Depends(get_db),
):
    email_clean = email.strip().lower()

    if action == "request_code":
        user = (
            db.query(User)
            .filter(User.email == email_clean, User.rol == ROL_ESTUDIANTE)
            .first()
        )
        if user:
            now = datetime.now(timezone.utc)
            reset = db.get(PasswordReset, user.id)
            if reset is None or _as_utc(reset.created_at) <= now - PASSWORD_RESET_COOLDOWN:
                if reset is None:
                    reset = PasswordReset(
                        user_id=user.id,
                        code_digest="",
                        expires_at=now + PASSWORD_RESET_TTL,
                        attempts=0,
                    )
                    db.add(reset)
                reset_code = f"{secrets.randbelow(1_000_000):06d}"
                reset.code_digest = _password_reset_digest(email_clean, reset_code)
                reset.expires_at = now + PASSWORD_RESET_TTL
                reset.attempts = 0
                db.commit()
                services.mailing.send_email(
                    user.email,
                    "Restablecer contraseña - Módulo Habitar",
                    (
                        f"Hola {user.nombre_completo},\n\n"
                        f"Tu código para restablecer la contraseña es: {reset_code}\n"
                        "El código vence en 15 minutos y se puede usar una sola vez."
                    ),
                )
                if settings.ENVIRONMENT == "development":
                    logger.info(
                        "Código de recuperación para %s: %s",
                        user.email,
                        reset_code,
                    )

        return _render_password_reset(
            request,
            email=email_clean,
            message=(
                "Si existe una cuenta de estudiante con ese email, recibirás "
                "un código. Ingresalo abajo para elegir una contraseña nueva."
            ),
            show_code_form=True,
        )

    if action != "reset_password":
        return _render_password_reset(
            request, email=email_clean, error="Solicitud inválida."
        )

    reset = (
        db.query(PasswordReset)
        .join(User, User.id == PasswordReset.user_id)
        .filter(User.email == email_clean, User.rol == ROL_ESTUDIANTE)
        .first()
    )
    invalid_message = "El código es inválido o venció. Solicitá uno nuevo."
    if reset is None:
        return _render_password_reset(
            request, email=email_clean, error=invalid_message, show_code_form=True
        )

    now = datetime.now(timezone.utc)
    if (
        _as_utc(reset.expires_at) <= now
        or reset.attempts >= PASSWORD_RESET_MAX_ATTEMPTS
    ):
        db.delete(reset)
        db.commit()
        return _render_password_reset(
            request, email=email_clean, error=invalid_message, show_code_form=True
        )

    if not hmac.compare_digest(
        reset.code_digest, _password_reset_digest(email_clean, code.strip())
    ):
        reset.attempts += 1
        if reset.attempts >= PASSWORD_RESET_MAX_ATTEMPTS:
            db.delete(reset)
        db.commit()
        return _render_password_reset(
            request, email=email_clean, error=invalid_message, show_code_form=True
        )

    if len(password) < 8:
        return _render_password_reset(
            request,
            email=email_clean,
            error="La contraseña debe tener al menos 8 caracteres.",
            show_code_form=True,
        )
    if password != password_confirm:
        return _render_password_reset(
            request,
            email=email_clean,
            error="Las contraseñas no coinciden.",
            show_code_form=True,
        )

    user = db.get(User, reset.user_id)
    if user is None:
        db.delete(reset)
        db.commit()
        return _render_password_reset(
            request, email=email_clean, error=invalid_message, show_code_form=True
        )

    user.pw_hash = hash_password(password)
    db.delete(reset)
    db.commit()
    return redirect_to(
        request,
        "login_form",
        query_params={"msg": "Contraseña restablecida. Ya podés ingresar."},
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = services.identity.authenticate(db, email, password)
    if not user:
        return render(request, "auth/login.html", error="Email o contraseña incorrectos.", email=email)
    login_user(request, user)

    if user.rol == ROL_ESTUDIANTE and (
        user.carrera_id is None or user.debe_cambiar_pw
    ):
        return redirect_to(request, "seleccionar_carrera_form")

    return redirect_to(request, "root")


@router.get("/signup")
def signup_form(request: Request):
    return render(request, "auth/signup.html")


@router.post("/signup")
def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    carrera: str = Form(""),
    db: Session = Depends(get_db),
):
    carrera_id = services.carreras.get_carreras_desde_dropdown(carreras_input=[carrera], db=db)[0].id
    try:
        user = services.identity.create_student(
            db,email=email, password=password,
            nombre=nombre, apellido=apellido, carrera_id=carrera_id,
        )
    except services.identity.SignupError as exc:
        return render(
            request, "auth/signup.html", error=str(exc),
            email=email, nombre=nombre, apellido=apellido, carrera=carrera,
        )
    login_user(request, user)
    return redirect_to(
        request, "home",
        query_params={"msg": "¡Cuenta creada! Bienvenido/a al Módulo Habitar."},
    )


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return redirect_to(request, "login_form")


@router.get("/perfil")
def perfil(request: Request, user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    return render(request, "auth/perfil.html", user=user, db=db)


@router.post("/perfil")
def perfil_update(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):

    user.nombre = nombre.strip()
    user.apellido = apellido.strip()
    db.commit()
    return redirect_to(
        request, "perfil",
        query_params={"msg": "Perfil actualizado."},
    )

@router.get("/seleccionar-carrera", name="seleccionar_carrera_form")
def seleccionar_carrera_form(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user_required_base),
):
    if user.carrera_id is not None and not user.debe_cambiar_pw:
        return redirect_to(request, "root")

    carreras = services.carreras.get_carreras(db)
    return render(
        request,
        "auth/seleccionar_carrera.html",
        user=user,
        db=db,
        carreras=carreras,
    )


@router.post("/seleccionar-carrera", name="seleccionar_carrera_submit")
def seleccionar_carrera_submit(
    request: Request,
    password: str = Form(...),
    password_confirm: str = Form(...),
    carrera_id: int = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user_required_base),
):
    carreras = services.carreras.get_carreras(db)
    if len(password) < 8:
        return render(
            request,
            "auth/seleccionar_carrera.html",
            user=user,
            db=db,
            carreras=carreras,
            error="La contraseña debe tener al menos 8 caracteres.",
        )
    if password != password_confirm:
        return render(
            request,
            "auth/seleccionar_carrera.html",
            user=user,
            db=db,
            carreras=carreras,
            error="Las contraseñas no coinciden.",
        )

    carrera = db.get(Carrera, carrera_id)
    if not carrera:
        return render(
            request,
            "auth/seleccionar_carrera.html",
            user=user,
            db=db,
            carreras=carreras,
            error="Debes seleccionar una carrera válida.",
        )

    user.pw_hash = hash_password(password)
    user.debe_cambiar_pw = False
    user.carrera_id = carrera.id
    db.commit()

    return redirect_to(request, "root")