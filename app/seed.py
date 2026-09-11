"""Idempotent demo seed: SIU legajos, staff/students, actividades, FAQ, config, carreras."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Actividad,
    AppConfig,
    Asistencia,
    Carrera,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Faq,
    ROL_COORDINACION,
    ROL_DIRECTOR,
    ROL_DOCENTE,
    ROL_ESTUDIANTE,
    TIPO_PRESENCIAL,
    TIPO_VIRTUAL,
    TipoCarrera,
    User,
    ValidLegajo,
)
from app.security import hash_password

DEMO_PASSWORD = "habitar123"

LEGAJOS = [
    ("1001", "Ana Pérez"),
    ("1002", "Bruno Díaz"),
    ("1003", "Carla Gómez"),
    ("1004", "Diego López"),
    ("1005", "Elena Ruiz"),
    ("1006", "Federico Sosa"),
    ("1007", "Gabriela Núñez"),
    ("1008", "Hernán Torres"),
    ("2001", "Julián Fraga"),
    ("2002", "Martín Groisman"),
]

CARRERAS = [
    ("Ambiental", "Ingeniería"),
    ("Biomédica", "Ingeniería"),
    ("Electrónica", "Ingeniería"),
    ("Energía", "Ingeniería"),
    ("Industrial", "Ingeniería"),
    ("Sistemas Espaciales", "Ingeniería"),
    ("Telecomunicaciones", "Ingeniería"),
    ("Transporte", "Ingeniería"),
    ("Desarrollo de Software", "Licenciatura"),
    ("Biotecnología", "Licenciatura"),
    ("Ciencia de Datos", "Licenciatura"),
    ("Física Médica", "Licenciatura"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_or_create_user(db: Session, email: str, **fields) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user

    rol = fields.get("rol", None)
    if rol is None:
        raise ValueError(f"Debe asignarse un rol al usuario asociado a {email}")

    carreras = fields.get("carreras", [])
    if rol == ROL_ESTUDIANTE and not carreras:
        raise ValueError(f"Debe asignarse una o más carreras al usuario asociado a {email} por ser de tipo Estudiante")

    user = User(email=email, pw_hash=hash_password(DEMO_PASSWORD), **fields)
    db.add(user)
    db.flush()
    return user


def seed_all(db: Session) -> None:
    # --- Tipos de Carrera ---
    tipos_map = {}
    for tipo_nombre in ["Licenciatura", "Ingeniería"]:
        tipo_obj = db.query(TipoCarrera).filter(TipoCarrera.nombre == tipo_nombre).first()
        if not tipo_obj:
            tipo_obj = TipoCarrera(nombre=tipo_nombre)
            db.add(tipo_obj)
            db.flush()
        tipos_map[tipo_nombre] = tipo_obj.id

    # --- Carreras ---
    if db.query(Carrera).count() == 0:
        for nombre_carrera, tipo_nombre in CARRERAS:
            tipo_id = tipos_map[tipo_nombre]
            db.add(Carrera(nombre=nombre_carrera, tipo_id=tipo_id))

    # --- SIU legajos (mock) ---
    if db.query(ValidLegajo).count() == 0:
        for legajo, nombre in LEGAJOS:
            db.add(ValidLegajo(legajo=legajo, nombre=nombre))

    # --- app config ---
    if db.get(AppConfig, "required_credits") is None:
        db.add(AppConfig(key="required_credits", value=str(settings.REQUIRED_CREDITS)))

    # --- FAQ ---
    if db.query(Faq).count() == 0:
        db.add_all(
            [
                Faq(orden=1, pregunta="¿Cómo me inscribo en una actividad?",
                    respuesta="Entrá a 'Actividades', abrí el detalle y tocá 'Inscribirme'. El sistema controla el cupo automáticamente."),
                Faq(orden=2, pregunta="¿Cómo registro mi asistencia?",
                    respuesta="En la actividad, el docente muestra un código QR. Abrí 'Registrar asistencia' y escaneá o ingresá el código de 6 dígitos."),
                Faq(orden=3, pregunta="¿Cuántos créditos necesito para aprobar?",
                    respuesta=f"Necesitás {settings.REQUIRED_CREDITS} créditos. Podés ver tu progreso en el inicio."),
                Faq(orden=4, pregunta="¿Puedo darme de baja de una actividad?",
                    respuesta="Sí, desde el detalle de la actividad podés liberar tu cupo si no vas a asistir."),
            ]
        )

    # --- users ---
    coord = _get_or_create_user(
        db, "coordinacion@unsam.edu.ar", nombre="Laura", apellido="Rasia",
        rol=ROL_COORDINACION, legajo=None,
    )
    docente = _get_or_create_user(
        db, "docente@unsam.edu.ar", nombre="Pablo", apellido="Méndez",
        rol=ROL_DOCENTE, legajo=None,
    )
    _get_or_create_user(
        db, "director@unsam.edu.ar", nombre="Marcela", apellido="Vega",
        rol=ROL_DIRECTOR, legajo=None,
    )

    lic_datos = db.query(Carrera).filter(Carrera.nombre == 'Ciencia de Datos').first()

    ing_electronica = (
        db.query(Carrera)
        .join(TipoCarrera)
        .filter(
            Carrera.nombre == "Electrónica",
            TipoCarrera.nombre == "Ingeniería"
        )
        .first()  # Devuelve la instancia de Carrera o None
    )

    ana = _get_or_create_user(
        db, "ana@alumno.unsam.edu.ar", nombre="Ana", apellido="Pérez",
        rol=ROL_ESTUDIANTE, legajo="1001", dni="40111222", carreras=[lic_datos],
    )
    bruno = _get_or_create_user(
        db, "bruno@alumno.unsam.edu.ar", nombre="Bruno", apellido="Díaz",
        rol=ROL_ESTUDIANTE, legajo="1002", dni="40333444", carreras=[lic_datos, ing_electronica],
    )
    db.flush()

    # --- actividades (only seed once) ---
    if db.query(Actividad).count() == 0:
        now = _now()
        carrera_1 = db.query(Carrera).get(1)
        carrera_2 = db.query(Carrera).get(2)
        carrera_3 = db.query(Carrera).get(3)
        acts = [
            Actividad(
                titulo="Bienvenida al campus",
                descripcion="Recorrido guiado por la ECyT y presentación del Módulo Habitar.",
                tipo=TIPO_PRESENCIAL, fecha_inicio=now - timedelta(days=7),
                fecha_fin=now - timedelta(days=7) + timedelta(hours=2),
                lugar="Hall central - Campus Miguelete", docente_id=docente.id,
                creditos=2, cupo_max=40, estado=ESTADO_PUBLICADA, created_by=coord.id,carreras_asociadas = [lic_datos,carrera_1, carrera_2]
            ),
            Actividad(
                titulo="Taller de hábitos de estudio",
                descripcion="Estrategias para organizar el tiempo y estudiar en la universidad.",
                tipo=TIPO_PRESENCIAL, fecha_inicio=now + timedelta(hours=24),
                fecha_fin=now + timedelta(hours=26),
                lugar="Aula 12 - Tornavía", docente_id=docente.id,
                creditos=3, cupo_max=2, estado=ESTADO_PUBLICADA, created_by=coord.id,carreras_asociadas = [lic_datos, carrera_1, carrera_2]
            ),
            Actividad(
                titulo="Charla: vida universitaria",
                descripcion="Egresados cuentan su experiencia y responden preguntas.",
                tipo=TIPO_VIRTUAL, fecha_inicio=now + timedelta(days=5),
                fecha_fin=now + timedelta(days=5) + timedelta(hours=1, minutes=30),
                lugar="Zoom (link por mail)", docente_id=docente.id,
                creditos=2, cupo_max=100, estado=ESTADO_PUBLICADA, created_by=coord.id,carreras_asociadas =[carrera_1, carrera_3]
            ),
            Actividad(
                titulo="Laboratorio abierto de Física",
                descripcion="Experiencias prácticas en el laboratorio de física.",
                tipo=TIPO_PRESENCIAL, fecha_inicio=now + timedelta(days=10),
                fecha_fin=now + timedelta(days=10) + timedelta(hours=3),
                lugar="Lab 3 - Pabellón de Física", docente_id=docente.id,
                creditos=4, cupo_max=15, estado=ESTADO_PUBLICADA, created_by=coord.id,carreras_asociadas = [carrera_1, carrera_2]
            ),
            Actividad(
                titulo="Borrador: Taller de escritura",
                descripcion="Pendiente de revisión, todavía sin publicar.",
                tipo=TIPO_PRESENCIAL, fecha_inicio=now + timedelta(days=14),
                fecha_fin=now + timedelta(days=14) + timedelta(hours=2),
                lugar="Aula 5", docente_id=docente.id,
                creditos=2, cupo_max=20, estado="borrador", created_by=coord.id,carreras_asociadas = [carrera_3]
            ),
            Actividad(
                titulo="Taller de Python",
                descripcion="Pendiente de revisión, todavía sin publicar.",
                tipo=TIPO_PRESENCIAL, fecha_inicio=now + timedelta(days=14),
                fecha_fin=now + timedelta(days=14) + timedelta(hours=2),
                lugar="Aula 5", docente_id=docente.id,
                creditos=2, cupo_max=20, estado="borrador", created_by=coord.id,carreras_asociadas = [carrera_3, carrera_2]
            ),
        ]
        db.add_all(acts)
        db.flush()

        bienvenida, taller, charla = acts[0], acts[1], acts[2]
        # Ana attended the welcome (past) -> has credits, and is enrolled in upcoming ones.
        db.add_all([
            Inscripcion(actividad_id=bienvenida.id, user_id=ana.id, estado=INSCRIPCION_ALTA),
            Inscripcion(actividad_id=taller.id, user_id=ana.id, estado=INSCRIPCION_ALTA),
            Inscripcion(actividad_id=charla.id, user_id=ana.id, estado=INSCRIPCION_ALTA),
            Inscripcion(actividad_id=bienvenida.id, user_id=bruno.id, estado=INSCRIPCION_ALTA),
        ])
        db.add(Asistencia(actividad_id=bienvenida.id, user_id=ana.id, validated_by=docente.id))

    db.commit()