from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Faq(Base):
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregunta: Mapped[str] = mapped_column(String(300))
    respuesta: Mapped[str] = mapped_column(Text)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    categoria_id: Mapped[int | None] = mapped_column(
        ForeignKey("faq_categorias.id", ondelete="SET NULL"), nullable=True, index=True
    )

    categoria = relationship("FaqCategoria", back_populates="preguntas")

    @property
    def tags_list(self) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in self.tags.split(",") if tag.strip()))


class FaqCategoria(Base):
    __tablename__ = "faq_categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    preguntas = relationship("Faq", back_populates="categoria")
