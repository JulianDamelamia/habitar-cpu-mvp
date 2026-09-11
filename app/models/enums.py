from enum import StrEnum


class Rol(StrEnum):
    ESTUDIANTE = "estudiante"
    COORDINACION = "coordinacion"
    DOCENTE = "docente"
    DIRECTOR = "director"


class TipoActividad(StrEnum):
    PRESENCIAL = "presencial"
    VIRTUAL = "virtual"


class EstadoActividad(StrEnum):
    BORRADOR = "borrador"
    PUBLICADA = "publicada"
    CANCELADA = "cancelada"


class EstadoInscripcion(StrEnum):
    INSCRIPTO = "inscripto"
    BAJA = "baja"


CARRERAS_ASOCIADAS_DEFAULT = "todas"

# Compatibility aliases for existing callers and persisted string values.
ROL_ESTUDIANTE = Rol.ESTUDIANTE
ROL_COORDINACION = Rol.COORDINACION
ROL_DOCENTE = Rol.DOCENTE
ROL_DIRECTOR = Rol.DIRECTOR
ROLES = tuple(Rol)
TIPO_PRESENCIAL = TipoActividad.PRESENCIAL
TIPO_VIRTUAL = TipoActividad.VIRTUAL
ESTADO_BORRADOR = EstadoActividad.BORRADOR
ESTADO_PUBLICADA = EstadoActividad.PUBLICADA
ESTADO_CANCELADA = EstadoActividad.CANCELADA
INSCRIPCION_ALTA = EstadoInscripcion.INSCRIPTO
INSCRIPCION_BAJA = EstadoInscripcion.BAJA
CARRERAS_ASOCIADAS_DEFALUT = CARRERAS_ASOCIADAS_DEFAULT
