from sqlalchemy import Column, ForeignKey, Table

from app.database import Base


user_carrera = Table(
    "user_carrera",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("carrera_id", ForeignKey("carreras.id", ondelete="CASCADE"), primary_key=True),
)

actividad_carrera = Table(
    "actividad_carrera",
    Base.metadata,
    Column("actividad_id", ForeignKey("actividades.id", ondelete="CASCADE"), primary_key=True),
    Column("carrera_id", ForeignKey("carreras.id", ondelete="CASCADE"), primary_key=True),
)
