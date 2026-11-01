from __future__ import annotations


from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.persona import Persona
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.carrera import Carrera
    from app.models.docente import Docente
    from app.models.estudiante import Estudiante
from app.models.enums import ROL_ESTUDIANTE


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("persona_id", name="uq_users_persona_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id"), nullable=False)
    pw_hash: Mapped[str] = mapped_column(String(255))
    debe_cambiar_pw: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    persona: Mapped["Persona"] = relationship(back_populates="usuario", uselist=False)
    estudiante: Mapped["Estudiante | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    rol: Mapped[str] = mapped_column(String(20), default=ROL_ESTUDIANTE, index=True)

    @property
    def nombre_completo(self) -> str:
        name = f"{self.nombre} {self.apellido}".strip()
        return name or self.email or ""

    @property
    def nombre(self) -> str:
        return self.persona.nombre if self.persona else ""
    @nombre.setter
    def nombre(self, value: str) -> None:
        if self.persona is None:
            self.persona = Persona(nombre="", apellido="", email="")
        self.persona.nombre = value.strip()

    @property
    def apellido(self) -> str:
        return self.persona.apellido if self.persona else ""

    @apellido.setter
    def apellido(self, value: str) -> None:
        if self.persona is None:
            self.persona = Persona(nombre="", apellido="", email="")
        self.persona.apellido = value.strip()

    @property
    def email(self) -> str | None:
        return self.persona.email if self.persona else None

    @email.setter
    def email(self, value: str | None) -> None:
        if self.persona is None:
            if value is None:
                return
            self.persona = Persona(nombre="", apellido="", email=value.strip())
        else:
            self.persona.email = value.strip() if value else None

    @property
    def carrera_id(self) -> int | None:
        return self.estudiante.carrera_id if self.estudiante else None

    @carrera_id.setter
    def carrera_id(self, value: int | None) -> None:
        if self.estudiante is None:
            from app.models.estudiante import Estudiante

            self.estudiante = Estudiante()
        self.estudiante.carrera_id = value

    @property
    def carrera(self) -> "Carrera | None":
        return self.estudiante.carrera if self.estudiante else None

    @carrera.setter
    def carrera(self, value: "Carrera | None") -> None:
        if self.estudiante is None:
            from app.models.estudiante import Estudiante

            self.estudiante = Estudiante()
        self.estudiante.carrera = value

    @property
    def docente(self) -> "Docente | None":
        return self.persona.docente if self.persona else None

    @property
    def docente_id(self) -> int | None:
        return self.docente.id if self.docente else None


def _normalizar_nombre(nombre: str | None, apellido: str | None) -> tuple[str, str]:
    nombre_limpio = " ".join((nombre or "").split())
    apellido_limpio = " ".join((apellido or "").split())
    return nombre_limpio.casefold(), apellido_limpio.casefold()


# @event.listens_for(Session, "before_flush")
# def _asociar_usuarios_con_docentes(
#     session: Session, _flush_context: object, _instances: object
# ) -> None:
#     '''Asocia automáticamente los usuarios con docentes existentes o crea nuevos docentes según el nombre y apellido del usuario.'''
#     from app.models.docente import Docente

#     usuarios = [
#         obj for obj in session.new.union(session.dirty) if isinstance(obj, User)
#     ]
#     if not usuarios:
#         return

#     docentes = session.query(Docente).all()
#     docentes.extend(
#         obj
#         for obj in session.new
#         if isinstance(obj, Docente) and obj not in docentes
#     )
#     por_nombre = {
#         _normalizar_nombre(docente.nombre, docente.apellido): docente
#         for docente in docentes
#     }

#     for usuario in usuarios:
#         clave = _normalizar_nombre(usuario.nombre, usuario.apellido)
#         docente = por_nombre.get(clave)
#         if (usuario.rol or ROL_ESTUDIANTE) == ROL_ESTUDIANTE:
#             if docente is not None:
#                 usuario.docente = docente
#             continue

#         if docente is None:
#             docente = Docente(
#                 nombre=" ".join((usuario.nombre or "").split()),
#                 apellido=" ".join((usuario.apellido or "").split()),
#             )
#             session.add(docente)
#             por_nombre[clave] = docente
#         usuario.docente = docente
