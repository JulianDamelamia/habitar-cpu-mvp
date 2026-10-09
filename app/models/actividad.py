from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import actividad_carrera
from app.models.enums import ESTADO_BORRADOR, TIPO_PRESENCIAL
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.docente import Docente
    from app.models.inscripcion import Inscripcion
    from app.models.user import User


class Actividad(Base):
    __tablename__ = "actividades"
    __table_args__ = (
        CheckConstraint(
            "creditos > 0 AND creditos * 2 = CAST(creditos * 2 AS INTEGER)",
            name="ck_actividades_creditos_positivo_multiplo_medio",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    tipo: Mapped[str] = mapped_column(String(20), default=TIPO_PRESENCIAL)
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fecha_fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lugar: Mapped[str] = mapped_column(String(200), default="")
    creditos: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=Decimal("1.0")
    )
    encuesta_obligatoria: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    cupo_max: Mapped[int] = mapped_column(Integer, default=30)
    estado: Mapped[str] = mapped_column(String(20), default=ESTADO_BORRADOR, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    docentes: Mapped[list["Docente"]] = relationship(
        secondary="actividad_docente", back_populates="actividades"
    )
    inscripciones: Mapped[list["Inscripcion"]] = relationship(
        back_populates="actividad", cascade="all, delete-orphan"
    )
    carreras_asociadas: Mapped[list["Carrera"]] = relationship(
        secondary=actividad_carrera,
        back_populates="actividades",
    )
