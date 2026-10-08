from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.estudiante import Estudiante
from app.models.enums import ROL_ESTUDIANTE


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    pw_hash: Mapped[str] = mapped_column(String(255))
    nombre: Mapped[str] = mapped_column(String(120), default="")
    apellido: Mapped[str] = mapped_column(String(120), default="")
    debe_cambiar_pw: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    estudiante: Mapped["Estudiante | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    rol: Mapped[str] = mapped_column(String(20), default=ROL_ESTUDIANTE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def nombre_completo(self) -> str:
        name = f"{self.nombre} {self.apellido}".strip()
        return name or self.email


    @property
    def carrera_id(self) -> int | None:
        return self.estudiante.carrera_id if self.estudiante else None

    @carrera_id.setter
    def carrera_id(self, carrera_id: int | None) -> None:
        if self.estudiante is None:
            from app.models.estudiante import Estudiante

            self.estudiante = Estudiante()
        self.estudiante.carrera_id = carrera_id

    @property
    def carrera(self) -> "Carrera | None":
        return self.estudiante.carrera if self.estudiante else None

    @carrera.setter
    def carrera(self, carrera: "Carrera | None") -> None:
        if self.estudiante is None:
            from app.models.estudiante import Estudiante

            self.estudiante = Estudiante()
        self.estudiante.carrera = carrera
