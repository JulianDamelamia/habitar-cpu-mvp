"""FastAPI application entrypoint for the Módulo Habitar platform."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    ROL_COORDINACION,
    ROL_DIRECTOR,
    ROL_DOCENTE,
    ROL_ESTUDIANTE,
)
from app.routers import main_router
# from app.routers.admin import admin_actividades, admin_carreras, admin_enroll

from app.scheduler import start_scheduler
from app.security import NotAuthenticated, NotAuthorized,CarreraPendienteException, get_current_user
from app.seed import seed_all
from app.templating import redirect_to, render

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
@app.exception_handler(CarreraPendienteException)
async def carrera_pendiente_exception_handler(request: Request, exc: CarreraPendienteException):
    # Usas tu helper pasando el nombre del endpoint (ej. "seleccionar_carrera_form")
    return redirect_to(request, "seleccionar_carrera_form")

@app.exception_handler(NotAuthenticated)
async def _not_authenticated(request: Request, _exc: NotAuthenticated):
    return redirect_to(request, "login_form")


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
app.include_router(main_router)


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
        return redirect_to(request, "login_form")
    if user.rol == ROL_ESTUDIANTE and (
        user.carrera_id is None or user.debe_cambiar_pw
    ):
        return redirect_to(request, "seleccionar_carrera_form")
    if user.rol == ROL_COORDINACION:
        return redirect_to(request, "panel")
    if user.rol == ROL_DOCENTE:
        return redirect_to(request, "docente_home")
    if user.rol == ROL_DIRECTOR:
        return redirect_to(request, "dashboard")
    return redirect_to(request, "home")

if __name__ == "__main__":
    import uvicorn
    # Arranca el servidor ASGI localmente en el puerto 8000
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)