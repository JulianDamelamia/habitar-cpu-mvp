"""FastAPI application entrypoint for the Módulo Habitar platform."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    ROL_COORDINACION,
    ROL_DIRECTOR,
    ROL_DOCENTE,
)
from app.routers import (
    admin_actividades,
    admin_carreras,
    admin_enroll,
    analytics,
    asistencia,
    auth,
    discovery,
    faq,
    inscripcion,
)
from app.scheduler import start_scheduler
from app.security import NotAuthenticated, NotAuthorized, get_current_user
from app.seed import seed_all
from app.templating import render

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("habitar.startup")


def _init_database(attempts: int = 5, delay: float = 2.0) -> None:
    """Create tables and seed, with a bounded retry so a cold Neon endpoint can wake."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            Base.metadata.create_all(bind=engine)
            db = SessionLocal()
            try:
                seed_all(db)
            finally:
                db.close()
            return
        except Exception as exc:  # noqa: BLE001 - retry transient DB/cold-start errors
            last = exc
            log.warning("DB init attempt %d/%d failed: %s", i + 1, attempts, exc)
            time.sleep(delay)
    if last is not None:
        raise last


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Never let a cold/unavailable DB abort the boot: the health check must pass so
    # Render keeps the service up, and request-time access retries once Neon is warm.
    try:
        _init_database()
    except Exception:  # noqa: BLE001
        log.exception("Database init/seed failed at startup; continuing so the app can boot.")
    try:
        start_scheduler()
    except Exception:  # noqa: BLE001
        log.exception("Scheduler failed to start.")
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ---- Auth control-flow -> friendly redirects -------------------------------
@app.exception_handler(NotAuthenticated)
async def _not_authenticated(request: Request, _exc: NotAuthenticated):
    return RedirectResponse(url="/login", status_code=303)


@app.exception_handler(NotAuthorized)
async def _not_authorized(request: Request, _exc: NotAuthorized):
    return render(request, "errors/403.html", status_code=403)


@app.exception_handler(IntegrityError)
async def _integrity_error(request: Request, _exc: IntegrityError):
    # Backstop: per-route handlers catch the expected conflicts; this prevents
    # any uncaught constraint violation from leaking a raw 500 traceback.
    return render(request, "errors/500.html", status_code=500)


@app.exception_handler(SQLAlchemyError)
async def _db_error(request: Request, exc: SQLAlchemyError):
    # A connection drop (e.g. Neon waking mid-request) must not leak a raw 500.
    log.warning("Database error on %s: %s", request.url.path, exc)
    return render(request, "errors/500.html", status_code=500)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s", request.url.path)
    return render(request, "errors/500.html", status_code=500)


# ---- Routers ----------------------------------------------------------------
app.include_router(auth.router)
app.include_router(discovery.router)
app.include_router(inscripcion.router)
app.include_router(asistencia.router)
app.include_router(admin_actividades.router)
app.include_router(admin_carreras.router)
app.include_router(admin_enroll.router)
app.include_router(analytics.router)
app.include_router(faq.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def root(request: Request):
    db = SessionLocal()
    try:
        user = get_current_user(request, db)
    finally:
        db.close()
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.rol == ROL_COORDINACION:
        return RedirectResponse(url="/admin", status_code=303)
    if user.rol == ROL_DOCENTE:
        return RedirectResponse(url="/docente", status_code=303)
    if user.rol == ROL_DIRECTOR:
        return RedirectResponse(url="/analytics", status_code=303)
    return RedirectResponse(url="/home", status_code=303)

if __name__ == "__main__":
    import uvicorn
    # Arranca el servidor ASGI localmente en el puerto 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)