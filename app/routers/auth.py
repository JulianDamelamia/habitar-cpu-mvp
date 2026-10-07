"""E-01 Authentication & profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
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


@router.get("/login")
def login_form(request: Request):
    return render(request, "auth/login.html")


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