from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import INSCRIPCION_ALTA


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (UniqueConstraint("actividad_id", "user_id", name="uq_enroll_actividad_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    estado: Mapped[str] = mapped_column(String(20), default=INSCRIPCION_ALTA, index=True)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actividad: Mapped["Actividad"] = relationship(back_populates="inscripciones")
    user: Mapped["User"] = relationship()
