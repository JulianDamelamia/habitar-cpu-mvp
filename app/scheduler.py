"""APScheduler job: email a reminder 24h before each actividad (E-04, US-14)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.email_util import send_email
from app.models.models import (
    Actividad,
    ESTADO_PUBLICADA,
    Inscripcion,
    INSCRIPCION_ALTA,
    Notification,
)

logger = logging.getLogger("habitar.scheduler")
scheduler = BackgroundScheduler(timezone="UTC")


def send_reminders() -> None:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Remind for any upcoming actividad within the next ~24h that has not been
        # reminded yet. Using `now` as the lower bound (instead of now+23h) makes the
        # job self-healing: if the free-tier instance hibernated through the exact 24h
        # mark, the reminder is still sent on the next run instead of being lost.
        window_end = now + timedelta(hours=24)
        actividades = (
            db.query(Actividad)
            .filter(
                Actividad.estado == ESTADO_PUBLICADA,
                Actividad.fecha_inicio >= now,
                Actividad.fecha_inicio <= window_end,
            )
            .all()
        )
        sent = 0
        for actividad in actividades:
            inscripciones = (
                db.query(Inscripcion)
                .filter(
                    Inscripcion.actividad_id == actividad.id,
                    Inscripcion.estado == INSCRIPCION_ALTA,
                    Inscripcion.reminded.is_(False),
                )
                .all()
            )
            for enr in inscripciones:
                msg = (
                    f"Recordatorio: '{actividad.titulo}' comienza el "
                    f"{actividad.fecha_inicio.strftime('%d/%m/%Y %H:%M')} en {actividad.lugar or 'el campus'}."
                )
                # Persist the reminded flag + notification BEFORE the email side
                # effect, and commit per-enrollment, so a later DB failure can never
                # un-send an already-delivered reminder (no double-send).
                enr.reminded = True
                db.add(Notification(user_id=enr.user_id, mensaje=msg))
                db.commit()
                if enr.user and enr.user.email:
                    send_email(enr.user.email, "Recordatorio de actividad", msg)
                sent += 1
        if sent:
            logger.info("Sent %d actividad reminders", sent)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reminder job failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        send_reminders,
        "interval",
        hours=1,
        id="reminders",
        replace_existing=True,
        coalesce=True,            # collapse missed runs (after hibernation) into one
        misfire_grace_time=3600,  # still run a tick that fired late instead of skipping
    )
    scheduler.start()
    logger.info("Reminder scheduler started")
