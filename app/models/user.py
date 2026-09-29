from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database import Base
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from app.models.carrera import Carrera
from app.models.enums import ROL_ESTUDIANTE


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    dni: Mapped[int] = mapped_column(Integer, unique=True)
    pw_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(120), default="")
    apellido: Mapped[str] = mapped_column(String(120), default="")

    carrera_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("carreras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Relación Muchos a Uno (1 estudiante -> 1 carrera)
    carrera: Mapped[Optional["Carrera"]] = relationship(
        back_populates="estudiantes"
    )

    rol: Mapped[str] = mapped_column(String(20), default=ROL_ESTUDIANTE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def nombre_completo(self) -> str:
        name = f"{self.nombre} {self.apellido}".strip()
        return name or self.email


    @validates("carrera")
    def validate_carreras(self, key, carrera):
        return carrera
