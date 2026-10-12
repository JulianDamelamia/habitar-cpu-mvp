from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Faq(Base):
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    pregunta: Mapped[str] = mapped_column(String(300))
    respuesta: Mapped[str] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")

    @property
    def tags_list(self) -> list[str]:
        return list(dict.fromkeys(tag.strip() for tag in self.tags.split(",") if tag.strip()))
