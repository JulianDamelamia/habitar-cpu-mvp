"""E-01 Authentication & profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ROL_ESTUDIANTE, User
from app.security import (
    current_user_required,
    login_user,
    logout_user,
)
from app import services
from app.templating import render

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
    return RedirectResponse(url="/", status_code=303)


@router.get("/signup")
def signup_form(request: Request):
    return render(request, "auth/signup.html")


@router.post("/signup")
def signup_submit(
    request: Request,
    legajo: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    nombre: str = Form(...),
    apellido: str = Form(...),
    dni: str = Form(""),
    carrera: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        user = services.identity.create_student(
            db, legajo=legajo, email=email, password=password,
            nombre=nombre, apellido=apellido, dni=dni, carrera=carrera,
        )
    except services.identity.SignupError as exc:
        return render(
            request, "auth/signup.html", error=str(exc),
            legajo=legajo, email=email, nombre=nombre, apellido=apellido, dni=dni, carrera=carrera,
        )
    login_user(request, user)
    return RedirectResponse(url="/home?msg=¡Cuenta creada! Bienvenido/a al Módulo Habitar.", status_code=303)


@router.get("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse(url="/login", status_code=303)


@router.get("/perfil")
def perfil(request: Request, user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    # Student services.identity comes from the SIU, so it is read-only; staff accounts are
    # internal and can edit their own profile.
    editable = user.rol != ROL_ESTUDIANTE
    return render(request, "auth/perfil.html", user=user, db=db, editable=editable)


@router.post("/perfil")
def perfil_update(
    request: Request,
    nombre: str = Form(...),
    apellido: str = Form(...),
    dni: str = Form(""),
    carrera: str = Form(""),
    user: User = Depends(current_user_required),
    db: Session = Depends(get_db),
):
    if user.rol == ROL_ESTUDIANTE:
        # Services.identity data is sourced from the SIU; students cannot edit it here.
        return RedirectResponse(
            url="/perfil?err=Tus datos provienen del SIU Guaraní y no se editan desde la plataforma.",
            status_code=303,
        )
    user.nombre = nombre.strip()
    user.apellido = apellido.strip()
    user.dni = dni.strip() or None
    user.carrera = carrera.strip() or None
    db.commit()
    return RedirectResponse(url="/perfil?msg=Perfil actualizado.", status_code=303)
