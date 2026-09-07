"""SQLAlchemy ORM models for the Módulo Habitar platform."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Table, Column, ForeignKey
from app.database import Base

# ---- Role / status constants -------------------------------------------------
ROLE_ESTUDIANTE = "estudiante"
ROLE_COORDINACION = "coordinacion"
ROLE_DOCENTE = "docente"
ROLE_DIRECTOR = "director"
ROLES = (ROLE_ESTUDIANTE, ROLE_COORDINACION, ROLE_DOCENTE, ROLE_DIRECTOR)

TIPO_PRESENCIAL = "presencial"
TIPO_VIRTUAL = "virtual"

ESTADO_BORRADOR = "borrador"
ESTADO_PUBLICADA = "publicada"
ESTADO_CANCELADA = "cancelada"

ENROLL_INSCRIPTO = "inscripto"
ENROLL_BAJA = "baja"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    legajo: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    pw_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(120), default="")
    apellido: Mapped[str] = mapped_column(String(120), default="")
    dni: Mapped[str | None] = mapped_column(String(20))
    carrera: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(20), default=ROLE_ESTUDIANTE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def full_name(self) -> str:
        name = f"{self.nombre} {self.apellido}".strip()
        return name or self.email


class ValidLegajo(Base):
    """SIU Guaraní simulator: a legajo must exist here to register."""
    __tablename__ = "valid_legajos"

    legajo: Mapped[str] = mapped_column(String(32), primary_key=True)
    nombre: Mapped[str | None] = mapped_column(String(160))

# Tabla intermedia N:M entre Actividad y Carrera
actividad_carrera = Table(
    "actividad_carrera",
    Base.metadata,
    Column("actividad_id", ForeignKey("actividades.id", ondelete="CASCADE"), primary_key=True),
    Column("carrera_id", ForeignKey("carreras.id", ondelete="CASCADE"), primary_key=True),
)

class Actividad(Base):
    __tablename__ = "actividades"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    tipo: Mapped[str] = mapped_column(String(20), default=TIPO_PRESENCIAL)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lugar: Mapped[str] = mapped_column(String(200), default="")
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    creditos: Mapped[int] = mapped_column(Integer, default=1)
    cupo_max: Mapped[int] = mapped_column(Integer, default=30)
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_BORRADOR, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    docente: Mapped[User | None] = relationship(foreign_keys=[docente_id])
    inscripciones: Mapped[list[Inscripcion]] = relationship(
        back_populates="actividad", cascade="all, delete-orphan"
    )
    carreras_asociadas: Mapped[list[Carrera]] = relationship(
        secondary=actividad_carrera,
        back_populates="actividades"
    )

class TipoCarrera(Base):
    __tablename__ = 'tipos_carrera'

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # {Licenciatura,  Ingeniería}

    # relación uno a muchos con Carrera
    carreras = relationship("Carrera", back_populates="tipo")

    def __repr__(self):
        return f"<TipoCarrera(id={self.id}, nombre='{self.nombre}')>"
    
class Carrera(Base):
    __tablename__ = "carreras"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    tipo_id: Mapped[int] = mapped_column(Integer, ForeignKey('tipos_carrera.id'), nullable=False)

    # Relación muchos a uno con Tipo
    tipo = relationship("TipoCarrera", back_populates="carreras")
    
    actividades: Mapped[list[Actividad]] = relationship(
        secondary=actividad_carrera,
        back_populates="carreras_asociadas"
    )
    def __repr__(self) -> str:
        return f"<Carrera(id={self.id}, nombre='{self.nombre}', tipo_id={self.tipo_id})>"

    
class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (UniqueConstraint("actividad_id", "user_id", name="uq_enroll_actividad_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), default=ENROLL_INSCRIPTO, index=True)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actividad: Mapped[Actividad] = relationship(back_populates="inscripciones")
    user: Mapped[User] = relationship()


class SesionAsistencia(Base):
    """A docente-opened window producing a rotating token for QR check-in."""
    __tablename__ = "sesiones_asistencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actividad: Mapped[Actividad] = relationship()


class Asistencia(Base):
    __tablename__ = "asistencia"
    __table_args__ = (UniqueConstraint("actividad_id", "user_id", name="uq_asistencia_actividad_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actividad: Mapped[Actividad] = relationship()
    user: Mapped[User] = relationship(foreign_keys=[user_id])


class SurveyResponse(Base):
    __tablename__ = "survey_responses"
    __table_args__ = (UniqueConstraint("actividad_id", "user_id", name="uq_survey_actividad_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actividad: Mapped[Actividad] = relationship()


class Faq(Base):
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregunta: Mapped[str] = mapped_column(String(300))
    respuesta: Mapped[str] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(Integer, default=0)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mensaje: Mapped[str] = mapped_column(String(500))
    leido: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppConfig(Base):
    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
