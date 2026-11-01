from pydantic import BaseModel, Field

from app.models.enums import TIPO_PRESENCIAL


class ActividadForm(BaseModel):
    titulo: str
    descripcion: str = ""
    tipo: str = TIPO_PRESENCIAL
    fecha_inicio: str
    fecha_fin: str = ""
    duracion: str = ""
    modo_finalizacion: str = "duracion"
    lugar: str = ""
    docentes_ids: list[int] = Field(default_factory=list)
    docentes_nombres: list[str] = Field(default_factory=list)
    docentes_apellidos: list[str] = Field(default_factory=list)
    docentes_emails: list[str] = Field(default_factory=list)
    creditos: str = "1"
    cupo_max: int = 30
    encuesta_obligatoria: bool = True
    carreras_asociadas: list[str] = Field(default_factory=list)


class SignupForm(BaseModel):
    email: str
    password: str
    nombre: str
    apellido: str
    carrera: str = ""
