from typing import Optional
from sqlalchemy.orm import Session
from app.models.models import Carrera, TipoCarrera

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
    tipo: Optional[str] = None,
    tipo_id: Optional[int] = None
) -> Carrera:
    """Crea y guarda una nueva carrera en la base de datos.
    
    Acepta el tipo tanto por su nombre de catálogo ('tipo') como por su ID ('tipo_id').
    """
    tipo_id_validado = obtener_y_validar_tipo_id(db, tipo=tipo, tipo_id=tipo_id)
    nueva_carrera = Carrera(nombre=nombre, tipo_id=tipo_id_validado)
    
    db.add(nueva_carrera)
    db.commit()
    db.refresh(nueva_carrera)
    
    return nueva_carrera