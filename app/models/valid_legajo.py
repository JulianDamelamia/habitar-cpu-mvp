from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ValidLegajo(Base):
    """SIU Guaraní simulator: a legajo must exist here to register."""

    __tablename__ = "valid_legajos"

    legajo: Mapped[str] = mapped_column(String(32), primary_key=True)
    nombre: Mapped[str | None] = mapped_column(String(160))
