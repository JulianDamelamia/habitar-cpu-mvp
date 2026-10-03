"""E-01 Authentication & profile."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import (
    current_user_required,
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
