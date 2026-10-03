from fastapi import APIRouter, Depends
from app.routers.admin import admin_carreras, admin_actividades, admin_enroll, admin_usuarios,admin_analytics
from app.routers.faq import admin_faq_router
from app.security import REQUIERE_ADMIN

# Router principal que agrupa todo lo administrativo
admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(REQUIERE_ADMIN)]  # Protege TODAS las rutas hijas de una sola vez
)

# Incluir cada submódulo
admin_router.include_router(admin_actividades.router, prefix="/actividades", tags=["Admin - Actividades"])
admin_router.include_router(admin_carreras.router, prefix="/carreras", tags=["Admin - Carreras"])
admin_router.include_router(admin_enroll.router, prefix="/inscriptos", tags=["Admin - Inscriptos"])
admin_router.include_router(admin_usuarios.router, prefix="/usuarios", tags=["Admin - Usuarios"])
admin_router.include_router(admin_analytics.router, prefix="/analytics", tags=["Admin - Analíticas"])
admin_router.include_router(admin_faq_router, prefix="/faq", tags=["Admin - FAQ"])