from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Asistencia(Base):
    __tablename__ = "asistencia"
    __table_args__ = (UniqueConstraint("actividad_id", "user_id", name="uq_asistencia_actividad_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    validated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actividad: Mapped["Actividad"] = relationship()
    user: Mapped["User"] = relationship(foreign_keys=[user_id])
