"""E-05 QR asistencia (docente rotating code + student check-in) and E-06 survey."""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from urllib.parse import quote

import qrcode
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Actividad,
    Asistencia,
    ESTADO_PUBLICADA,
    ROLE_COORDINACION,
    SurveyResponse,
    User,
)
from app.security import current_user_required, require_roles
from app.services import asistencia as asistencia_svc
from app.services import inscripcion as enrollment_svc
from app.templating import render

router = APIRouter()


def _qr_data_uri(text: str) -> str:
    img = qrcode.make(text)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _can_manage(actividad: Actividad, user: User) -> bool:
    return user.role == ROLE_COORDINACION or actividad.docente_id == user.id


# ---- Student check-in --------------------------------------------------------
@router.get("/checkin")
def checkin_page(request: Request, user: User = Depends(require_roles("estudiante")), db: Session = Depends(get_db)):
    return render(request, "student/checkin.html", user=user, db=db)


@router.post("/checkin")
def checkin_submit(
    request: Request,
    codigo: str = Form(...),
    user: User = Depends(require_roles("estudiante")),
    db: Session = Depends(get_db),
):
    try:
        actividad = asistencia_svc.check_in(db, codigo, user.id)
    except asistencia_svc.AsistenciaError as exc:
        return RedirectResponse(url=f"/checkin?err={quote(str(exc))}", status_code=303)
    return RedirectResponse(
        url=f"/actividades/{actividad.id}/encuesta?msg=¡Asistencia registrada! Sumaste {actividad.creditos} créditos.",
        status_code=303,
    )


# ---- Survey (E-06) -----------------------------------------------------------
@router.get("/actividades/{actividad_id}/encuesta")
def survey_form(
    request: Request,
    actividad_id: int,
    user: User = Depends(require_roles("estudiante")),
    db: Session = Depends(get_db),
):
    actividad = db.get(Actividad, actividad_id)
    if actividad is None:
        return RedirectResponse(url="/home", status_code=303)
    attended = (
        db.query(Asistencia)
        .filter(Asistencia.actividad_id == actividad_id, Asistencia.user_id == user.id)
        .first()
    )
    if not attended:
        return RedirectResponse(url="/home?err=Solo podés responder la encuesta de actividades a las que asististe.", status_code=303)
    answered = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.actividad_id == actividad_id, SurveyResponse.user_id == user.id)
        .first()
    )
    return render(request, "student/encuesta.html", user=user, db=db, a=actividad, answered=answered)


@router.post("/actividades/{actividad_id}/encuesta")
def survey_submit(
    request: Request,
    actividad_id: int,
    rating: int = Form(...),
    comment: str = Form(""),
    user: User = Depends(require_roles("estudiante")),
    db: Session = Depends(get_db),
):
    attended = (
        db.query(Asistencia)
        .filter(Asistencia.actividad_id == actividad_id, Asistencia.user_id == user.id)
        .first()
    )
    if not attended:
        return RedirectResponse(url="/home?err=No podés responder esta encuesta.", status_code=303)
    existing = (
        db.query(SurveyResponse)
        .filter(SurveyResponse.actividad_id == actividad_id, SurveyResponse.user_id == user.id)
        .first()
    )
    rating = max(1, min(5, rating))
    comment_val = comment.strip() or None
    if existing:
        existing.rating = rating
        existing.comment = comment_val
        db.commit()
    else:
        db.add(SurveyResponse(actividad_id=actividad_id, user_id=user.id, rating=rating, comment=comment_val))
        try:
            db.commit()
        except IntegrityError:
            # Concurrent double-submit: a row was inserted between our check and commit.
            db.rollback()
            row = (
                db.query(SurveyResponse)
                .filter(SurveyResponse.actividad_id == actividad_id, SurveyResponse.user_id == user.id)
                .first()
            )
            if row:
                row.rating = rating
                row.comment = comment_val
                db.commit()
    return RedirectResponse(url="/home?msg=¡Gracias por tu opinión!", status_code=303)


# ---- Docente asistencia session ---------------------------------------------
@router.get("/docente")
def docente_home(
    request: Request,
    user: User = Depends(require_roles("docente", "coordinacion")),
    db: Session = Depends(get_db),
):
    q = db.query(Actividad).filter(Actividad.estado == ESTADO_PUBLICADA)
    if user.role != ROLE_COORDINACION:
        q = q.filter(Actividad.docente_id == user.id)
    actividades = q.order_by(Actividad.fecha_inicio.desc()).all()
    return render(request, "docente/home.html", user=user, db=db, actividades=actividades)


@router.get("/docente/actividades/{actividad_id}/asistencia")
def docente_asistencia(
    request: Request,
    actividad_id: int,
    user: User = Depends(require_roles("docente", "coordinacion")),
    db: Session = Depends(get_db),
):
    actividad = db.get(Actividad, actividad_id)
    if actividad is None or not _can_manage(actividad, user):
        return RedirectResponse(url="/docente?err=Actividad no encontrada.", status_code=303)
    inscriptos = enrollment_svc.inscriptos(db, actividad_id)
    present = asistencia_svc.present_user_ids(db, actividad_id)
    return render(
        request, "docente/asistencia.html", user=user, db=db,
        a=actividad, inscriptos=inscriptos, present=present,
    )


@router.get("/docente/actividades/{actividad_id}/token")
def docente_token(
    request: Request,
    actividad_id: int,
    user: User = Depends(require_roles("docente", "coordinacion")),
    db: Session = Depends(get_db),
):
    actividad = db.get(Actividad, actividad_id)
    if actividad is None or not _can_manage(actividad, user):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    sess = asistencia_svc.open_or_rotate(db, actividad_id, user.id)
    exp = sess.expires_at if sess.expires_at.tzinfo else sess.expires_at.replace(tzinfo=timezone.utc)
    seconds_left = max(int((exp - datetime.now(timezone.utc)).total_seconds()), 0)
    return JSONResponse({"token": sess.token, "qr": _qr_data_uri(sess.token), "seconds_left": seconds_left})


@router.post("/docente/actividades/{actividad_id}/marcar/{student_id}")
def docente_mark(
    request: Request,
    actividad_id: int,
    student_id: int,
    user: User = Depends(require_roles("docente", "coordinacion")),
    db: Session = Depends(get_db),
):
    actividad = db.get(Actividad, actividad_id)
    if actividad is None or not _can_manage(actividad, user):
        return RedirectResponse(url="/docente?err=Actividad no encontrada.", status_code=303)
    try:
        asistencia_svc.mark_present_manual(db, actividad_id, student_id, user.id)
    except asistencia_svc.AsistenciaError as exc:
        return RedirectResponse(url=f"/docente/actividades/{actividad_id}/asistencia?err={quote(str(exc))}", status_code=303)
    return RedirectResponse(url=f"/docente/actividades/{actividad_id}/asistencia?msg=Asistencia registrada.", status_code=303)
