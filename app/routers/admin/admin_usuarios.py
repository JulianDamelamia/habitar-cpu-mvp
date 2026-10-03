
from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app import services
from app.database import get_db
from app.models.user import User
from app.security import REQUIERE_ADMIN
from app.templating import redirect_to, render
router = APIRouter()

@router.get("")
def crear_usuarios(request: Request, user: User = Depends(REQUIERE_ADMIN), db: Session = Depends(get_db)):
    return render(request, "admin/usuarios.html", user=user, db=db)

@router.post("/import")
async def generacion_usuarios(
    request: Request,
    background_tasks: BackgroundTasks,
    archivo: UploadFile = File(...),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    try:
        df = await services.inscripcion.leer_tabla_usuarios(archivo)
        services.inscripcion.validar_datos_usuarios(df)
        retorno = services.identity.procesar_carga_masiva(db=db, df=df)
        usuarios_creados = retorno.get('usuarios_creados',[])
        cant_usuarios_creados = len(usuarios_creados)
        errores = retorno.get('errores',[])
        notificaciones_mail = retorno.get('notificaciones_mail', [])

        if errores:
            return render(
                request, 
                "admin/usuarios.html",
                user=user, 
                db=db, 
                errores=errores, 
                err=f"Se detectaron {len(errores)} filas con errores. Por favor corregilas y reintentá.",
                status_code=400
            )
        if usuarios_creados:
            # mailing
            background_tasks.add_task(
                services.mailing.enviar_mails_verificacion,
                contenido = notificaciones_mail
            )

    except ValueError as e:
        return render(
            request, 
            "admin/usuarios.html",
            user=user, 
            db=db, 
            err=str(e), 
            status_code=400
        )
    return redirect_to(
        request, "crear_usuarios",
        query_params={"msg": f"Creados {cant_usuarios_creados} usuarios nuevos."},
    )
