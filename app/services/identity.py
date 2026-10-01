"""Identity / SIU-mock service. Single swap point for real SIU Guaraní integration."""
from __future__ import annotations
from typing import NamedTuple

import pandas as pd
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import ROL_ESTUDIANTE, User#, ValidLegajo
from app.models.carrera import Carrera
from app.security import hash_password, verify_password


class SignupError(Exception):
    pass


# def legajo_is_valid(db: Session, legajo: str) -> bool:
#     """SIU Guaraní simulator lookup."""
#     return db.get(ValidLegajo, legajo.strip()) is not None
class DatosExistentes(NamedTuple):
    emails: set[str]
    dnis: set[int]

def get_datos_existentes(db: Session, emails: set[str], dnis: set[int]) -> DatosExistentes:
    if not emails and not dnis:
        return DatosExistentes(emails=set(), dnis=set())

    # Trae únicamente los campos 'email' y 'dni' para minimizar transferencia de datos
    results = (
        db.query(User.email, User.dni)
        .filter(or_(User.email.in_(emails), User.dni.in_(dnis)))
        .all()
    )

    emails_existentes:set[str] = {r.email.lower() for r in results if r.email}
    dnis_existentes:set[int] = {r.dni for r in results if r.dni is not None}

    return DatosExistentes(emails=emails_existentes, dnis=dnis_existentes)

def email_taken(db: Session, email: str) -> bool:
    return db.query(User).filter(User.email == email.lower().strip()).first() is not None

def dni_duplicado(db:Session, dni:int) -> bool:
    return db.query(User).filter(User.dni == dni).first() is not None

#TODO: create_studen y el script de carga masiva podrían reutilizar algo de código pero no es prioritario
def create_student(
    db: Session,
    *,
    email: str,
    password: str,
    nombre: str,
    apellido: str,
    dni: int,
    carrera_id: int,
) -> User:
    email_clean = email.lower().strip()

    # Validar unicidad de email y DNI en una ÚNICA consulta a la BD
    datos_existentes = get_datos_existentes(db, emails={email_clean}, dnis={dni})

    if email_clean in datos_existentes.emails:
        raise SignupError("Ya existe una cuenta con ese email.")
    if dni in datos_existentes.dnis:
        raise SignupError("El número de DNI está asociado a otro email.")

    user = User(
        email=email_clean,
        pw_hash=hash_password(password),
        nombre=nombre.strip(),
        apellido=apellido.strip(),
        dni=dni,
        carrera_id=carrera_id,
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

def validar_email(email, existentes, seen_emails_in_file):
    if not email or email == 'nan':
        return "Email requerido"
    elif email in existentes.emails:
        return "El email ya existe en la base de datos"
    elif email in seen_emails_in_file:
        return "El email está duplicado dentro del mismo archivo"
    return None

def validar_dni(dni, existentes, seen_dnis_in_file):
    if pd.isna(dni):
        return"DNI inválido o requerido"
    elif dni in existentes.dnis:
        return"El DNI ya existe en la base de datos"
    elif dni in seen_dnis_in_file:
        return"El DNI está duplicado dentro del mismo archivo"
    return None

from app.services.consultas_comunes import get_carreras
from rapidfuzz import process, fuzz
class CarreraMatcher:
    def __init__(self, carreras: list[Carrera]):
        self.carreras = carreras
        self.choices: dict[str, Carrera] = {}

        # Generamos combinaciones posibles para mejorar las coincidencias
        for c in carreras:
            tipo_nombre = c.tipo.nombre if c.tipo else ""
            
            # Opción 1: "Ingeniería Ambiental"
            combinada_1 = f"{tipo_nombre} {c.nombre}".strip().lower()
            # Opción 2: "Ambiental" (por si no ponen el tipo)
            combinada_2 = c.nombre.strip().lower()

            self.choices[combinada_1] = c
            self.choices[combinada_2] = c

    def resolver_id_carrera(self, carrera_texto: str, score_corte: float = 65.0) -> int | None:
        """
        Retorna el ID de la carrera si la similitud supera el score_corte.
        De lo contrario, retorna None.
        """
        if not carrera_texto or not str(carrera_texto).strip():
            return None

        texto_limpio = str(carrera_texto).strip().lower()

        # WRatio maneja diferencias de orden, minúsculas/mayúsculas y substrings
        resultado = process.extractOne(
            texto_limpio,
            self.choices.keys(),
            scorer=fuzz.WRatio
        )

        if resultado:
            coincidencia, score, _ = resultado
            if score >= score_corte:
                return self.choices[coincidencia].id

        return None

def procesar_carga_masiva(
    db: Session, 
    df: pd.DataFrame, 
) -> dict[str, list]:
    
    # Clean up inicial de strings
    df['email_clean'] = df['email'].astype(str).str.lower().str.strip()
    df['dni_clean'] = pd.to_numeric(df['dni'], errors='coerce').astype('Int64')

    archivo_emails = set(df['email_clean'].dropna())
    archivo_dnis = set(df['dni_clean'].dropna())

    # 1. Traer de la BD en UNA sola query los emails/DNIs que ya existen
    existentes = get_datos_existentes(db, emails=archivo_emails, dnis=archivo_dnis)

    usuarios_a_crear: list[User] = []
    errores: list[dict] = []
    
    # Sets para detectar duplicados dentro del mismo archivo
    seen_emails_in_file = set()
    seen_dnis_in_file = set()
    
    #inicializo matcher
    lista_de_carreras = get_carreras(db)
    matcher = CarreraMatcher(lista_de_carreras)

    for idx, row in df.iterrows():
        email = row['email_clean']
        dni = row['dni_clean']
        nombre = str(row.get('nombre', '')).strip()
        apellido = str(row.get('apellido', '')).strip()
        carrera_id = matcher.resolver_id_carrera(row['carrera'])
        row_errors = []
        errores_email = validar_email(email, existentes, seen_emails_in_file)
        if errores_email is not None:
            row_errors.append(errores_email)

        errores_dni = validar_dni(dni, existentes, seen_dnis_in_file)
        if errores_dni is not None:
            row_errors.append(errores_dni)

        if row_errors:
            errores.append({"fila": idx, "email": email, "dni":dni, "errores": row_errors})
            continue

        # Si pasa todas las validaciones:
        seen_emails_in_file.add(email)
        seen_dnis_in_file.add(dni)

        # Crear la entidad User
        user = User(
            email=email,
            pw_hash=hash_password(str(dni)),
            nombre=nombre,
            apellido=apellido,
            dni=int(dni),
            carrera_id=carrera_id,
            rol=ROL_ESTUDIANTE,
        )
        usuarios_a_crear.append(user)

    # 3. Guardar masivamente en la BD en una sola transacción
    if usuarios_a_crear and not errores:  
        db.add_all(usuarios_a_crear)
        db.commit()

    return {
        "usuarios_creados": usuarios_a_crear,#type:ignore
        "errores": errores,
        
    }