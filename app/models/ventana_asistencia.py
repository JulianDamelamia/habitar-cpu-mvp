from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VentanaAsistencia(Base):
    __tablename__ = "ventanas_asistencia"
    __table_args__ = (
        UniqueConstraint("actividad_id", name="uq_ventana_asistencia_actividad"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(
        ForeignKey("actividades.id", ondelete="CASCADE"), index=True
    )
    codigo: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    codigo_cierre: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    cerrada_manualmente: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    correos_enviados: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
