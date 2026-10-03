"""E-09 Inscripcion & asistencia supervision, CSV/XLSX import-export (coordination)."""
from __future__ import annotations
import io
import pandas as pd
from fastapi import APIRouter, Depends,Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import REQUIERE_ADMIN
from app import services 

from app.templating import redirect_to, render

router = APIRouter()

#TODO: esto dónde va? en servicios?
def _inscriptos_dataframe(db: Session, actividad_id: int) -> pd.DataFrame:
    inscriptos = services.inscripcion.inscriptos(db, actividad_id)
    present = services.asistencia.present_user_ids(db, actividad_id)
    data = [
        {
            "apellido": e.user.apellido,
            "nombre": e.user.nombre,
            "email": e.user.email,
            "asistio": "sí" if e.user_id in present else "no",
        }
        for e in inscriptos
    ]
    return pd.DataFrame(data, columns=["apellido", "nombre", "email", "asistio"])


@router.get("")
def inscriptos_index(request: Request, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    items = services.actividades.list_all(db)
    rows = [{"a": a, "cupo": services.actividades.cupo_info(db, a)} for a in items]
    return render(request, "admin/inscriptos_index.html", user=user, db=db, rows=rows)


@router.get("/{actividad_id}")
def inscriptos_detail(request: Request, actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    a = services.actividades.get(db, actividad_id)
    if a is None:
        return redirect_to(
            request, "inscriptos_index",
            query_params={"err": "Actividad no encontrada."},
        )
    inscriptos = services.inscripcion.inscriptos(db, actividad_id)
    present = services.asistencia.present_user_ids(db, actividad_id)
    return render(
        request, "admin/inscriptos_detail.html", user=user, db=db,
        a=a, inscriptos=inscriptos, present=present,
    )


@router.get("/{actividad_id}/export.csv")
def export_csv(actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    df = _inscriptos_dataframe(db, actividad_id)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=inscriptos_{actividad_id}.csv"},
    )


@router.get("/{actividad_id}/export.xlsx")
def export_xlsx(actividad_id: int, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    df = _inscriptos_dataframe(db, actividad_id)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Inscriptos")
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=inscriptos_{actividad_id}.xlsx"},
    )