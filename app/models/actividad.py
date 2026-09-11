from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import actividad_carrera
from app.models.enums import ESTADO_BORRADOR, TIPO_PRESENCIAL


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
    docente: Mapped["User | None"] = relationship(foreign_keys=[docente_id])
    inscripciones: Mapped[list["Inscripcion"]] = relationship(
        back_populates="actividad", cascade="all, delete-orphan"
    )
    carreras_asociadas: Mapped[list["Carrera"]] = relationship(
        secondary=actividad_carrera,
        back_populates="actividades",
    )
