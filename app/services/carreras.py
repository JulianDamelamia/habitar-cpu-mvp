from typing import Optional
from sqlalchemy.orm import Session,contains_eager
from app.models import Carrera, TipoCarrera

def obtener_y_validar_tipo_id(
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
        
def add_carrera(
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

    tipo_id_validado = obtener_y_validar_tipo_id(db, tipo=tipo, tipo_id=tipo_id)
    nueva_carrera = Carrera(
        nombre=nombre,
        tipo_id=tipo_id_validado,
        creditos_requeridos=creditos_requeridos,
    )
    
    db.add(nueva_carrera)
    db.commit()
    db.refresh(nueva_carrera)
    
    return nueva_carrera

def get_carreras(db: Session) -> list[Carrera]:
    return (db.query(Carrera)
        .join(Carrera.tipo)
        .options(contains_eager(Carrera.tipo))
        .order_by(
            TipoCarrera.nombre.asc(),  
            Carrera.nombre.asc()
        )
        .all())

def resolver_carreras_desde_input(carreras_input: list[str], db: Session) -> list[Carrera]:
    """
    Convierte la entrada enviada por un Form (ej: ["1", "3"] o ["todas"]) 
    en una lista de instancias del modelo Carrera de SQLAlchemy.
    """
    if not carreras_input:
        return []

    if "todas" in carreras_input:
        return db.query(Carrera).all()

    carreras_ids = [int(c_id) for c_id in carreras_input if c_id.isdigit()]
    if not carreras_ids:
        return []

    carreras_encontradas = db.query(Carrera).filter(Carrera.id.in_(carreras_ids)).all()

    if len(carreras_encontradas) != len(set(carreras_ids)):
        raise ValueError("Una o más carreras especificadas no existen.")

    return carreras_encontradas

def get_creditos(carrera:Carrera) -> int:
    return carrera.creditos_requeridos