from fastapi import APIRouter
from app.routers import asistencia, auth, discovery, faq, inscripcion
from app.routers.admin import admin_router
# Router raíz que agrupa TODA la API
main_router = APIRouter()

# Incluir routers públicos/generales

main_router.include_router(asistencia.router)
main_router.include_router(auth.router)
main_router.include_router(discovery.router)
main_router.include_router(faq.router)
main_router.include_router(inscripcion.router)


# Incluir el router de administración (ya trae su /admin, tags y dependencias)
main_router.include_router(admin_router)