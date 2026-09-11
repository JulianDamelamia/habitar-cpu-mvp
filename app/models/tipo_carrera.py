from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoCarrera(Base):
    __tablename__ = "tipos_carrera"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    carreras = relationship("Carrera", back_populates="tipo")

    def __repr__(self):
        return f"<TipoCarrera(id={self.id}, nombre='{self.nombre}')>"
