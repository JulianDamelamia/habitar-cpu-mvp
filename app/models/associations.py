from sqlalchemy import Column, ForeignKey, Table

from app.database import Base

actividad_carrera = Table(
    "actividad_carrera",
    Base.metadata,
    Column("actividad_id", ForeignKey("actividades.id", ondelete="CASCADE"), primary_key=True),
    Column("carrera_id", ForeignKey("carreras.id", ondelete="CASCADE"), primary_key=True),
)
