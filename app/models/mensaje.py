from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(primary_key=True)
    remitente_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    destinatario_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asunto: Mapped[str] = mapped_column(String(200), nullable=False)
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    remitente = relationship("User", foreign_keys=[remitente_id])
    destinatario = relationship("User", foreign_keys=[destinatario_id])
    lecturas = relationship(
        "MensajeLectura", back_populates="mensaje", cascade="all, delete-orphan"
    )


class MensajeLectura(Base):
    __tablename__ = "mensaje_lecturas"

    mensaje_id: Mapped[int] = mapped_column(
        ForeignKey("mensajes.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    leido: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    leido_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    mensaje = relationship("Mensaje", back_populates="lecturas")
    user = relationship("User")
