"""E-09 Inscripcion & asistencia supervision, CSV/XLSX import-export (coordination)."""
from __future__ import annotations

import io
from typing import List

import pandas as pd
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User#, ValidLegajo
from app.security import requiere_roles
from app import services 

from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")


def _inscriptos_dataframe(db: Session, actividad_id: int) -> pd.DataFrame:
    inscriptos = services.inscripcion.inscriptos(db, actividad_id)
    present = services.asistencia.present_user_ids(db, actividad_id)
    data = [
        {
            "dni": e.user.dni,
            "apellido": e.user.apellido,
            "nombre": e.user.nombre,
            "email": e.user.email,
            "asistio": "sí" if e.user_id in present else "no",
        }
        for e in inscriptos
    ]
    return pd.DataFrame(data, columns=["dni", "apellido", "nombre", "email", "asistio"])


@router.get("/admin/inscriptos")
def inscriptos_index(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    items = services.actividades.list_all(db)
    rows = [{"a": a, "cupo": services.actividades.cupo_info(db, a)} for a in items]
    return render(request, "admin/inscriptos_index.html", user=user, db=db, rows=rows)


@router.get("/admin/inscriptos/{actividad_id}")
def inscriptos_detail(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin/inscriptos?err=Actividad no encontrada.", status_code=303)
    inscriptos = services.inscripcion.inscriptos(db, actividad_id)
    present = services.asistencia.present_user_ids(db, actividad_id)
    return render(
        request, "admin/inscriptos_detail.html", user=user, db=db,
        a=a, inscriptos=inscriptos, present=present,
    )


@router.get("/admin/inscriptos/{actividad_id}/export.csv")
def export_csv(actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    df = _inscriptos_dataframe(db, actividad_id)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=inscriptos_{actividad_id}.csv"},
    )


@router.get("/admin/inscriptos/{actividad_id}/export.xlsx")
def export_xlsx(actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    df = _inscriptos_dataframe(db, actividad_id)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Inscriptos")
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inscriptos_{actividad_id}.xlsx"},
    )


async def _leer_tabla_usuarios(archivo:UploadFile)-> pd.DataFrame:
    raw = await archivo.read()
    if archivo.filename.lower().endswith(".xlsx"): # type: ignore
        df = pd.read_excel(io.BytesIO(raw))
    df = pd.read_csv(io.BytesIO(raw))
    return df
COLUMNAS_ESPERADAS = {'dni', 'email', 'nombre', 'apellido', 'carrera'}
def _validar_datos_usuarios(df:pd.DataFrame) -> None:
    """Validación síncrona de columnas y formatos."""
    cols = {str(c).lower().strip() for c in df.columns}
    if cols != COLUMNAS_ESPERADAS:
        faltantes = COLUMNAS_ESPERADAS - cols
        raise ValueError(f"El archivo debe contener las columnas {faltantes}.")
    
# def _agregar_usuarios(df: pd.DataFrame, db: Session = Depends(get_db)) -> int:
#     cols = {c.lower().strip(): c for c in df.columns}
#     contador:int = 0
#     seen: set[str] = set()  # dedupe within the file (autoflush=False -> db.get won't see pending inserts)
#     for _, row in df.iterrows():
#         dni = str(row[cols["dni"]]).strip()
#         if not dni or dni.lower() == "nan":
#             continue
#         if "." in dni:  # pandas may read ints as floats
#             dni = dni.split(".")[0]
#         if dni in seen:
#             continue
#         seen.add(dni)
#         nombre = str(row[cols["nombre"]]).strip() if "nombre" in cols else None
#         apellido = str(row[cols["apellido"]]).strip() if "apellido" in cols else None

#         if db.get(User, dni) is None:
#             contrasena_temporal = dni
#             db.add(User(**params))
#             contador += 1
#     return contador

@router.get("/admin/crear_usuarios")
def crear_usuarios(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    return render(request, "admin/crear_usuarios.html", user=user, db=db)

@router.post("/admin/crear_usuarios/import")       
async def generacion_usuarios(
    request: Request,
    archivo: UploadFile = File(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db)
):
    try:
        df = await _leer_tabla_usuarios(archivo)
        _validar_datos_usuarios(df)
        retorno = services.identity.procesar_carga_masiva(db=db, df=df)
        cant_usuarios_creados = retorno['creados']
        errores = retorno['errores']
        if errores:
            return render(
                request, 
                "admin/crear_usuarios.html", 
                user=user, 
                db=db, 
                errores=errores, 
                err=f"Se detectaron {len(errores)} filas con errores. Por favor corregilas y reintentá.",
                status_code=400
            )
            
    except ValueError as e:
        return render(
            request, 
            "admin/crear_usuarios.html", 
            user=user, 
            db=db, 
            err=str(e), 
            status_code=400
        )
    return RedirectResponse(url=f"/admin/crear_usuarios?msg=Creados {cant_usuarios_creados} usuarios nuevos.", status_code=303)
    

# @router.post("/admin/legajos/import")
# async def legajos_import(
#     request: Request,
#     archivo: UploadFile = File(...),
#     user: User = Depends(ADMIN),
#     db: Session = Depends(get_db),
# ):
#     raw = await archivo.read()
#     try:
#         if archivo.filename.lower().endswith(".xlsx"): # type: ignore
#             df = pd.read_excel(io.BytesIO(raw))
#         else:
#             df = pd.read_csv(io.BytesIO(raw))
#     except Exception:  # noqa: BLE001
#         return RedirectResponse(url="/admin/legajos?err=No se pudo leer el archivo. Debe ser CSV o XLSX.", status_code=303)

#     cols = {c.lower().strip(): c for c in df.columns}
#     if "legajo" not in cols:
#         return RedirectResponse(url="/admin/legajos?err=El archivo debe tener una columna 'legajo'.", status_code=303)

#     added = 0
#     seen: set[str] = set()  # dedupe within the file (autoflush=False -> db.get won't see pending inserts)
#     for _, row in df.iterrows():
#         legajo = str(row[cols["legajo"]]).strip()
#         if not legajo or legajo.lower() == "nan":
#             continue
#         if "." in legajo:  # pandas may read ints as floats
#             legajo = legajo.split(".")[0]
#         if legajo in seen:
#             continue
#         seen.add(legajo)
#         nombre = str(row[cols["nombre"]]).strip() if "nombre" in cols else None
#         if db.get(ValidLegajo, legajo) is None:
#             db.add(ValidLegajo(legajo=legajo, nombre=nombre))
#             added += 1
#     try:
#         db.commit()
#     except IntegrityError:
#         # Concurrent import added an overlapping legajo; nothing is corrupted.
#         db.rollback()
#         return RedirectResponse(url="/admin/legajos?err=Algunos legajos ya existían. Reintentá.", status_code=303)
#     return RedirectResponse(url=f"/admin/legajos?msg=Importados {added} legajos nuevos.", status_code=303)
