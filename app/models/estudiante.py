from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Estudiante(Base):
    __tablename__ = "estudiantes"
    __table_args__ = (
        CheckConstraint("creditos_acreditados >= 0", name="ck_estudiante_creditos_acreditados"),
        CheckConstraint("creditos_requeridos > 0", name="ck_estudiante_creditos_requeridos"),
        CheckConstraint("creditos_penalizacion >= 0", name="ck_estudiante_creditos_penalizacion"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    carrera_id: Mapped[int | None] = mapped_column(
        ForeignKey("carreras.id", ondelete="SET NULL"), nullable=True, index=True
    )
    creditos_acreditados: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )
    creditos_requeridos: Mapped[float] = mapped_column(
        Float, nullable=False, default=10.0, server_default=text("10")
    )
    creditos_penalizacion: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0")
    )

    user: Mapped["User"] = relationship(back_populates="estudiante")
    carrera: Mapped["Carrera | None"] = relationship(back_populates="estudiantes")
