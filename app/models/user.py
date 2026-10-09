from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, event, func
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.docente import Docente
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
    docente_id: Mapped[int | None] = mapped_column(ForeignKey("docentes.id"), nullable=True)
    docente: Mapped["Docente | None"] = relationship(back_populates="usuarios")
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


def _normalizar_nombre(nombre: str | None, apellido: str | None) -> tuple[str, str]:
    nombre_limpio = " ".join((nombre or "").split())
    apellido_limpio = " ".join((apellido or "").split())
    return nombre_limpio.casefold(), apellido_limpio.casefold()


@event.listens_for(Session, "before_flush")
def _asociar_usuarios_con_docentes(
    session: Session, _flush_context: object, _instances: object
) -> None:
    from app.models.docente import Docente

    usuarios = [
        obj for obj in session.new.union(session.dirty) if isinstance(obj, User)
    ]
    if not usuarios:
        return

    docentes = session.query(Docente).all()
    docentes.extend(
        obj
        for obj in session.new
        if isinstance(obj, Docente) and obj not in docentes
    )
    por_nombre = {
        _normalizar_nombre(docente.nombre, docente.apellido): docente
        for docente in docentes
    }

    for usuario in usuarios:
        clave = _normalizar_nombre(usuario.nombre, usuario.apellido)
        docente = por_nombre.get(clave)
        if (usuario.rol or ROL_ESTUDIANTE) == ROL_ESTUDIANTE:
            if docente is not None:
                usuario.docente = docente
            continue

        if docente is None:
            docente = Docente(
                nombre=" ".join((usuario.nombre or "").split()),
                apellido=" ".join((usuario.apellido or "").split()),
            )
            session.add(docente)
            por_nombre[clave] = docente
        usuario.docente = docente
