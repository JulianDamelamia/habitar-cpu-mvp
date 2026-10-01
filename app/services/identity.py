"""Identity / SIU-mock service. Single swap point for real SIU Guaraní integration."""
from __future__ import annotations
import secrets
from typing import NamedTuple, Optional

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ROL_ESTUDIANTE, User#, ValidLegajo
from app.models.carrera import Carrera
from app.security import hash_password, verify_password


class SignupError(Exception):
    pass


def get_emails_registrados(db: Session, emails: set[str]) -> set[str]:
    if not emails :
        return set()
    results = (
        db.query(User.email)
        .filter(User.email.in_(emails))
        .all()
    )
    emails_existentes:set[str] = {r.email.lower() for r in results if r.email}
    return emails_existentes

def email_taken(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email.lower().strip()).first() is not None

#TODO: create_studen y el script de carga masiva podrían reutilizar algo de código pero no es prioritario
def create_student(
    db: Session,
    *,
    email: str,
    password: str,
    nombre: str,
    apellido: str,
    carrera_id:Optional[int] = None
) -> User:
    email_clean = email.lower().strip()

    # Validar unicidad de email BD
    datos_existentes = get_emails_registrados(db, emails={email_clean})

    if email_clean in datos_existentes:
        raise SignupError("Ya existe una cuenta con ese email.")

    user = User(
        email=email_clean,
        pw_hash=hash_password(password),
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        rol=ROL_ESTUDIANTE,
        carrera_id=carrera_id
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

def validar_email(email, existentes, seen_emails_in_file):
    if not email or email == 'nan':
        return "Email requerido"
    elif email in existentes:
        return "El email ya existe en la base de datos"
    elif email in seen_emails_in_file:
        return "El email está duplicado dentro del mismo archivo"
    return None

# def validar_dni(dni, existentes, seen_dnis_in_file):
#     if pd.isna(dni):
#         return"DNI inválido o requerido"
#     elif dni in existentes.dnis:
#         return"El DNI ya existe en la base de datos"
#     elif dni in seen_dnis_in_file:
#         return"El DNI está duplicado dentro del mismo archivo"
#     return None

# from app.services.consultas_comunes import get_carreras
# from rapidfuzz import process, fuzz
# class CarreraMatcher:
#     def __init__(self, carreras: list[Carrera]):
#         self.carreras = carreras
#         self.choices: dict[str, Carrera] = {}

#         # Generamos combinaciones posibles para mejorar las coincidencias
#         for c in carreras:
#             tipo_nombre = c.tipo.nombre if c.tipo else ""
            
#             # Opción 1: "Ingeniería Ambiental"
#             combinada_1 = f"{tipo_nombre} {c.nombre}".strip().lower()
#             # Opción 2: "Ambiental" (por si no ponen el tipo)
#             combinada_2 = c.nombre.strip().lower()

#             self.choices[combinada_1] = c
#             self.choices[combinada_2] = c

#     def resolver_id_carrera(self, carrera_texto: str, score_corte: float = 65.0) -> int | None:
#         """
#         Retorna el ID de la carrera si la similitud supera el score_corte.
#         De lo contrario, retorna None.
#         """
#         if not carrera_texto or not str(carrera_texto).strip():
#             return None

#         texto_limpio = str(carrera_texto).strip().lower()

#         # WRatio maneja diferencias de orden, minúsculas/mayúsculas y substrings
#         resultado = process.extractOne(
#             texto_limpio,
#             self.choices.keys(),
#             scorer=fuzz.WRatio
#         )

#         if resultado:
#             coincidencia, score, _ = resultado
#             if score >= score_corte:
#                 return self.choices[coincidencia].id

#         return None

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
            email=email,
            pw_hash=hash_password(contrasena_temporal),
            nombre=nombre,
            apellido=apellido,
            carrera_id=carrera_id,
            rol=ROL_ESTUDIANTE,
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