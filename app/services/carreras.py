from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session,contains_eager
from app.models import Carrera, TipoCarrera, User
from app.models.enums import ESTADO_BORRADOR, ROL_ESTUDIANTE

def _obtener_y_validar_tipo_id(
    db: Session, 
    tipo: Optional[str] = None, 
    tipo_id: Optional[int] = None
) -> int:
    """Valida la integridad del tipo de carrera y retorna el tipo_id definitivo."""

    # 1) Ningún parámetro
    if tipo_id is None and tipo is None:
        raise ValueError("Debe proporcionar 'tipo' (nombre) o 'tipo_id'.")
    
    tipo_str = tipo.strip() if tipo is not None else None

    # 2) Solo se pasa el nombre
    if tipo_id is None and tipo_str is not None:
        tipo_obj = db.query(TipoCarrera).filter(TipoCarrera.nombre.ilike(tipo_str.strip())).first()
        if not tipo_obj:
            raise ValueError(f"El tipo de carrera '{tipo_str}' no existe en el catálogo.")
        return tipo_obj.id

    # 3) Solo se pasa el ID
    if tipo_id is not None and tipo_str is None:
        tipo_obj = db.get(TipoCarrera, tipo_id)
        if not tipo_obj:
            raise ValueError(f"El tipo de carrera con ID '{tipo_id}' no existe en el catálogo.")
        return tipo_obj.id

    # 4) Se pasan ambos argumentos
    tipo_obj = db.get(TipoCarrera, tipo_id)
    if not tipo_obj:
        raise ValueError(f"El tipo de carrera con ID '{tipo_id}' no existe en el catálogo.")


    if tipo_obj.nombre.lower() != str(tipo_str).strip().lower():
        raise ValueError(
            f"Inconsistencia: El tipo_id {tipo_id} corresponde a '{tipo_obj.nombre}', "
            f"pero se envió el nombre '{tipo_str}'."
        )

    return tipo_obj.id


def _validar_nombre_unico(
    db: Session,
    nombre: str,
    tipo_id: int,
    carrera_id: int | None = None,
) -> str:
    nombre_limpio = nombre.strip()
    nombre_normalizado = nombre_limpio.casefold()
    carreras_del_tipo = db.query(Carrera).filter(Carrera.tipo_id == tipo_id).all()
    if any(
        carrera.id != carrera_id
        and carrera.nombre.strip().casefold() == nombre_normalizado
        for carrera in carreras_del_tipo
    ):
        tipo_obj = db.get(TipoCarrera, tipo_id)
        raise ValueError(
            f"La carrera '{tipo_obj.nombre} {nombre_limpio}' ya existe."
        )
    return nombre_limpio
        
def add(
    db: Session,
    nombre: str,
    creditos_requeridos: int,
    tipo: Optional[str] = None,
    tipo_id: Optional[int] = None
) -> Carrera:
    """Crea y guarda una nueva carrera en la base de datos.
    
    Acepta el tipo tanto por su nombre de catálogo ('tipo') como por su ID ('tipo_id').
    """
    if creditos_requeridos <= 0:
        raise ValueError("Los créditos requeridos deben ser mayores que cero.")

    tipo_id_validado = _obtener_y_validar_tipo_id(db, tipo=tipo, tipo_id=tipo_id)
    nombre_limpio = _validar_nombre_unico(db, nombre, tipo_id_validado)

    nueva_carrera = Carrera(
        nombre=nombre_limpio,
        tipo_id=tipo_id_validado,
        creditos_requeridos=creditos_requeridos,
    )
    
    db.add(nueva_carrera)
    db.commit()
    db.refresh(nueva_carrera)
    
    return nueva_carrera

def update(
    db: Session,
    carrera: Carrera,
    nombre: str,
    creditos_requeridos: int,
    tipo: Optional[str] = None,
    tipo_id: Optional[int] = None,
) -> Carrera:
    """Actualiza los datos de una carrera existente."""
    if creditos_requeridos <= 0:
        raise ValueError("Los créditos requeridos deben ser mayores que cero.")

    tipo_id_validado = _obtener_y_validar_tipo_id(db, tipo=tipo, tipo_id=tipo_id)
    nombre_limpio = _validar_nombre_unico(
        db, nombre, tipo_id_validado, carrera_id=carrera.id
    )

    carrera.nombre = nombre_limpio
    carrera.creditos_requeridos = creditos_requeridos
    carrera.tipo_id = tipo_id_validado

    db.commit()
    db.refresh(carrera)

    return carrera

def get_carreras_desde_dropdown(carreras_input: list[str], db: Session) -> list[Carrera]:
    """
    Convierte la entrada enviada por un Form (ej: ["1", "3"] o ["todas"]) 
    en una lista de instancias del modelo Carrera de SQLAlchemy.
    """
    if not carreras_input:
        return []

    if "todas" in carreras_input:
        return db.query(Carrera).all()

    carreras_ids = [int(c_id) for c_id in carreras_input]
    if not carreras_ids:
        return []

    carreras_encontradas = db.query(Carrera).filter(Carrera.id.in_(carreras_ids)).all()

    if len(carreras_encontradas) != len(set(carreras_ids)):
        raise ValueError("Una o más carreras especificadas no existen.")

    return carreras_encontradas

def get_carreras(db: Session) -> list[Carrera]:
    return (db.query(Carrera)
        .join(Carrera.tipo)
        .options(contains_eager(Carrera.tipo))
        .order_by(
            TipoCarrera.nombre.asc(),  
            Carrera.nombre.asc()
        )
        .all())

def get_by_id(db: Session, carrera_id: int) -> Carrera | None:
    return db.get(Carrera, carrera_id)

def get_cantidad_inscriptos_agrupados(db: Session) -> dict[str, int]:
    stmt = (
        select(
            Carrera.id,
            Carrera.nombre,
            Carrera.tipo,
            func.count(User.id).label("cantidad"),
        )
        .outerjoin(
            User,
            (User.carrera_id == Carrera.id) &
            (User.rol == ROL_ESTUDIANTE)
        )
        .group_by(Carrera.id, Carrera.nombre, Carrera.tipo)
    )

    rows = db.execute(stmt).all()

    return {
        f"{row.tipo.nombre} {row.nombre}": row.cantidad
        for row in rows
    }

def get_cantidad_inscriptos_por_carrera(db: Session, carrera_id: int) -> int:
    stmt = (
        select(func.count(User.id))
        .where(
            User.carrera_id == carrera_id,
            User.rol == ROL_ESTUDIANTE,
        )
    )

    return db.execute(stmt).scalar_one()


def eliminar(db: Session, carrera: Carrera) -> int:
    cantidad_inscriptos = get_cantidad_inscriptos_por_carrera(db, carrera.id)
    if cantidad_inscriptos:
        raise ValueError(
            f"no se puede eliminar la carrera porque tiene {cantidad_inscriptos} "
            "cantidad de inscriptos. Borre o rematricule los usuarios primero"
        )

    actividades = list(carrera.actividades)
    for actividad in actividades:
        actividad.carreras_asociadas.remove(carrera)
        if not actividad.carreras_asociadas:
            actividad.estado = ESTADO_BORRADOR

    db.delete(carrera)
    db.commit()
    return len(actividades)