"""Identity / SIU-mock service. Single swap point for real SIU Guaraní integration."""
from __future__ import annotations
from dataclasses import dataclass
import secrets

import pandas as pd
from sqlalchemy.orm import Session

from app.models import Estudiante, Persona, ROL_ESTUDIANTE, User

from app.security import hash_password, verify_password


class SignupError(Exception):
    pass


@dataclass(frozen=True)
class SignupContext:
    email: str
    password: str
    nombre: str
    apellido: str
    carrera_id: int | None


def get_emails_registrados(db: Session, emails: set[str]) -> set[str]:
    if not emails :
        return set()
    results = db.query(Persona.email).filter(Persona.email.in_(emails)).all()
    emails_existentes: set[str] = {email.lower() for (email,) in results if email}
    return emails_existentes

def email_taken(db: Session, email: str) -> bool:
    return (
        db.query(Persona.id)
        .filter(Persona.email == email.lower().strip())
        .first()
        is not None
    )

def create_student(
    db: Session,
    contexto: SignupContext,
) -> User:
    email_clean = contexto.email.lower().strip()

    # Validar unicidad de email BD
    datos_existentes = get_emails_registrados(db, emails={email_clean})

    if email_clean in datos_existentes:
        raise SignupError("Ya existe una cuenta con ese email.")

    user = User(
        persona=Persona(
            email=email_clean,
            nombre=contexto.nombre.strip(),
            apellido=contexto.apellido.strip(),
        ),
        pw_hash=hash_password(contexto.password),
        rol=ROL_ESTUDIANTE,
        estudiante=Estudiante(carrera_id=contexto.carrera_id),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = (
        db.query(User)
        .join(User.persona)
        .filter(Persona.email == email.lower().strip())
        .first()
        )
    if user and verify_password(password, user.pw_hash):
        return user
    return None

def validar_email(email, existentes, seen_emails_in_file):
    if not email or email == 'nan':
        return "Email requerido"
    elif email in existentes:
        return "El email ya existe en la base de datos"
    elif email in seen_emails_in_file:
        return "El email está duplicado dentro del mismo archivo"
    return None


def procesar_carga_masiva(
    db: Session,
    df: pd.DataFrame,
) -> dict[str, list]:
    """Procesa una carga masiva de usuarios desde un DataFrame.

    Normaliza y valida los emails de cada fila, evita duplicados dentro del
    archivo y contra la base de datos, y crea los usuarios nuevos con una
    contraseña temporal autogenerada. La función devuelve la lista de usuarios
    creados, los datos para notificar por email y los errores detectados.

    Args:
        db: Sesión activa de SQLAlchemy para persistir los usuarios.
        df: DataFrame con al menos las columnas ``email``, ``nombre`` y
            ``apellido`` para cada estudiante a registrar.

    Returns:
        Un diccionario con las claves:
        - ``usuarios_creados``: lista de instancias ``User`` creadas.
        - ``notificaciones_mail``: datos de cada usuario para enviar credenciales.
        - ``errores``: registros con fila y errores de validación.
    """

    df['email_clean'] = df['email'].astype(str).str.lower().str.strip()
    archivo_emails = set(df['email_clean'].dropna())
    existentes = get_emails_registrados(db, emails=archivo_emails)

    usuarios_a_crear: list[User] = []
    notificaciones_mail: list[dict] = []
    errores: list[dict] = []


    seen_emails_in_file = set()

    for idx, row in df.iterrows():
        email = row['email_clean']
        nombre = str(row.get('nombre', '')).strip()
        apellido = str(row.get('apellido', '')).strip()
        carrera_id = None
        row_errors = []

        errores_email = validar_email(email, existentes, seen_emails_in_file)
        if errores_email is not None:
            row_errors.append(errores_email)

        if row_errors:
            errores.append({"fila": idx, "email": email, "errores": row_errors})
            continue

        seen_emails_in_file.add(email)
        contrasena_temporal = f"{secrets.randbelow(1_000_000):06d}"

        user = User(
            persona=Persona(email=email, nombre=nombre, apellido=apellido),
            pw_hash=hash_password(contrasena_temporal),
            rol=ROL_ESTUDIANTE,
            estudiante=Estudiante(carrera_id=carrera_id),
        )
        usuarios_a_crear.append(user)

        notificaciones_mail.append({
            "email": email,
            "nombre": nombre,
            "apellido": apellido,
            "password_temporal": contrasena_temporal
        })

    if usuarios_a_crear and not errores:
        db.add_all(usuarios_a_crear)
        db.commit()

    return {
        "usuarios_creados": usuarios_a_crear,
        "notificaciones_mail": notificaciones_mail,
        "errores": errores,
    }