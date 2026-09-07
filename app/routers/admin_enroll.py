"""E-09 Inscripcion & asistencia supervision, CSV/XLSX import-export (coordination)."""
from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import User, ValidLegajo
from app.security import requiere_roles
from app.services import actividades as actividades_svc
from app.services import asistencia as asistencia_svc
from app.services import inscripcion as enrollment_svc
from app.templating import render

router = APIRouter()
ADMIN = requiere_roles("coordinacion")


def _inscriptos_dataframe(db: Session, actividad_id: int) -> pd.DataFrame:
    inscriptos = enrollment_svc.inscriptos(db, actividad_id)
    present = asistencia_svc.present_user_ids(db, actividad_id)
    data = [
        {
            "legajo": e.user.legajo or "",
            "apellido": e.user.apellido,
            "nombre": e.user.nombre,
            "email": e.user.email,
            "asistio": "sí" if e.user_id in present else "no",
        }
        for e in inscriptos
    ]
    return pd.DataFrame(data, columns=["legajo", "apellido", "nombre", "email", "asistio"])


@router.get("/admin/inscriptos")
def inscriptos_index(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    items = actividades_svc.list_all(db)
    rows = [{"a": a, "cupo": actividades_svc.cupo_info(db, a)} for a in items]
    return render(request, "admin/inscriptos_index.html", user=user, db=db, rows=rows)


@router.get("/admin/inscriptos/{actividad_id}")
def inscriptos_detail(request: Request, actividad_id: int, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    a = actividades_svc.get(db, actividad_id)
    if a is None:
        return RedirectResponse(url="/admin/inscriptos?err=Actividad no encontrada.", status_code=303)
    inscriptos = enrollment_svc.inscriptos(db, actividad_id)
    present = asistencia_svc.present_user_ids(db, actividad_id)
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


@router.get("/admin/legajos")
def legajos_page(request: Request, user: User = Depends(ADMIN), db: Session = Depends(get_db)):
    total = db.query(ValidLegajo).count()
    return render(request, "admin/legajos.html", user=user, db=db, total=total)


@router.post("/admin/legajos/import")
async def legajos_import(
    request: Request,
    archivo: UploadFile = File(...),
    user: User = Depends(ADMIN),
    db: Session = Depends(get_db),
):
    raw = await archivo.read()
    try:
        if archivo.filename.lower().endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            df = pd.read_csv(io.BytesIO(raw))
    except Exception:  # noqa: BLE001
        return RedirectResponse(url="/admin/legajos?err=No se pudo leer el archivo. Debe ser CSV o XLSX.", status_code=303)

    cols = {c.lower().strip(): c for c in df.columns}
    if "legajo" not in cols:
        return RedirectResponse(url="/admin/legajos?err=El archivo debe tener una columna 'legajo'.", status_code=303)

    added = 0
    seen: set[str] = set()  # dedupe within the file (autoflush=False -> db.get won't see pending inserts)
    for _, row in df.iterrows():
        legajo = str(row[cols["legajo"]]).strip()
        if not legajo or legajo.lower() == "nan":
            continue
        if "." in legajo:  # pandas may read ints as floats
            legajo = legajo.split(".")[0]
        if legajo in seen:
            continue
        seen.add(legajo)
        nombre = str(row[cols["nombre"]]).strip() if "nombre" in cols else None
        if db.get(ValidLegajo, legajo) is None:
            db.add(ValidLegajo(legajo=legajo, nombre=nombre))
            added += 1
    try:
        db.commit()
    except IntegrityError:
        # Concurrent import added an overlapping legajo; nothing is corrupted.
        db.rollback()
        return RedirectResponse(url="/admin/legajos?err=Algunos legajos ya existían. Reintentá.", status_code=303)
    return RedirectResponse(url=f"/admin/legajos?msg=Importados {added} legajos nuevos.", status_code=303)
