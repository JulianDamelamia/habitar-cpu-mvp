from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.persona import Persona

if TYPE_CHECKING:
    from app.models.actividad import Actividad
    from app.models.persona import Persona


class Docente(Base):
    __tablename__ = "docentes"
    __table_args__ = (UniqueConstraint("persona_id", name="uq_docentes_persona_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    persona_id: Mapped[int] = mapped_column(
        ForeignKey("personas.id"), nullable=False
    )
    #usuarios: Mapped[list[User]] = relationship(back_populates="docente")
    actividades: Mapped[list[Actividad]] = relationship(
        secondary="actividad_docente", back_populates="docentes"
    )
    persona: Mapped["Persona"] = relationship(back_populates="docente")
    @property
    def nombre_completo(self) -> str:
        return f"{self.persona.nombre} {self.persona.apellido}".strip()
    @property
    def email(self) -> str | None:
        return self.persona.email
