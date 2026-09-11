from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.associations import actividad_carrera, user_carrera


class Carrera(Base):
    __tablename__ = "carreras"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    creditos_requeridos: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipos_carrera.id"), nullable=False)
    tipo = relationship("TipoCarrera", back_populates="carreras")
    actividades: Mapped[list["Actividad"]] = relationship(
        secondary=actividad_carrera,
        back_populates="carreras_asociadas",
    )
    estudiantes: Mapped[list["User"]] = relationship(
        secondary=user_carrera,
        back_populates="carreras",
    )

    def __repr__(self) -> str:
        return f"<Carrera(id={self.id}, nombre='{self.nombre}', tipo_id={self.tipo_id})>"
