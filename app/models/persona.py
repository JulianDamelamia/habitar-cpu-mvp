from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


if TYPE_CHECKING:
    from app.models.actividad import Docente
    from app.models.user import User
    from app.models.estudiante import Estudiante



class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    apellido: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    usuario: Mapped["User | None"] = relationship(back_populates="persona", uselist=False)
    docente: Mapped["Docente | None"] = relationship(back_populates="usuarios")
    estudiante: Mapped["Estudiante | None"] = relationship(back_populates="persona", uselist=False)
    @property
    def nombre_completo(self) -> str:
        return f"{self.nombre} {self.apellido}".strip()
