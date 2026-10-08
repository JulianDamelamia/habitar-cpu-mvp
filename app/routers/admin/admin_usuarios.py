
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app import services
from app.database import get_db
from app.models import Carrera, Estudiante, ROL_ESTUDIANTE, User
from app.security import REQUIERE_ADMIN
from app.templating import redirect_to, render

router = APIRouter()


class CreditosRequeridosUpdate(BaseModel):
    creditos_requeridos: Decimal = Field(gt=0)

    @field_validator("creditos_requeridos")
    @classmethod
    def validate_credit_step(cls, value: Decimal) -> Decimal:
        if not value.is_finite() or value % Decimal("0.5") != 0:
            raise ValueError("Los créditos requeridos deben avanzar en pasos de 0,5.")
        return value


def _render_usuarios(
    request: Request,
    user: User,
    db: Session,
    *,
    busqueda: str = "",
    errores: list | None = None,
    err: str | None = None,
):
    estudiantes = []
    if busqueda:
        query = (
            db.query(User)
            .join(Estudiante, Estudiante.user_id == User.id)
            .options(selectinload(User.estudiante).selectinload(Estudiante.carrera))
            .filter(User.rol == ROL_ESTUDIANTE)
        )
        termino = f"%{busqueda.strip()}%"
        query = query.filter(
            or_(
                User.email.ilike(termino),
                User.nombre.ilike(termino),
                User.apellido.ilike(termino),
            )
        )
        estudiantes = query.order_by(
            User.apellido, User.nombre, User.email
        ).limit(50).all()
    return render(
        request,
        "admin/usuarios.html",
        user=user,
        db=db,
        estudiantes=estudiantes,
        carreras=services.carreras.get_carreras(db),
        busqueda=busqueda,
        errores=errores or [],
        form_error=err,
    )


@router.get("")
def crear_usuarios(
    request: Request,
    q: str = Query("", max_length=120),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    return _render_usuarios(request, user, db, busqueda=q.strip())


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
            response = _render_usuarios(
                request,
                user,
                db,
                errores=errores,
                err=f"Se detectaron {len(errores)} filas con errores. Por favor corregilas y reintentá.",
            )
            response.status_code = 400
            return response
        if usuarios_creados:
            # mailing
            background_tasks.add_task(
                services.mailing.enviar_mails_verificacion,
                contenido = notificaciones_mail
            )

    except ValueError as e:
        response = _render_usuarios(request, user, db, err=str(e))
        response.status_code = 400
        return response
    return redirect_to(
        request, "crear_usuarios",
        query_params={"msg": f"Creados {cant_usuarios_creados} usuarios nuevos."},
    )


@router.post("/{estudiante_id}/actualizar")
def actualizar_usuario(
    request: Request,
    estudiante_id: int,
    nombre: str = Form(...),
    apellido: str = Form(...),
    carrera_id: str = Form(""),
    q: str = Form(""),
    user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    estudiante = db.get(User, estudiante_id)
    if estudiante is None or estudiante.rol != ROL_ESTUDIANTE or estudiante.estudiante is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado.")

    nombre = nombre.strip()
    apellido = apellido.strip()
    if not nombre or not apellido or len(nombre) > 120 or len(apellido) > 120:
        return redirect_to(
            request,
            "crear_usuarios",
            query_params={"err": "Nombre y apellido son obligatorios y deben tener hasta 120 caracteres.", "q": q},
        )

    carrera: Carrera | None = None
    if carrera_id:
        try:
            carrera = db.get(Carrera, int(carrera_id))
        except ValueError:
            carrera = None
        if carrera is None:
            return redirect_to(
                request,
                "crear_usuarios",
                query_params={"err": "Seleccioná una carrera válida.", "q": q},
            )

    estudiante.nombre = nombre
    estudiante.apellido = apellido
    estudiante.estudiante.carrera = carrera
    db.commit()
    return redirect_to(
        request,
        "crear_usuarios",
        query_params={"msg": "Datos del estudiante actualizados.", "q": q},
    )


@router.patch("/{estudiante_id}/creditos-requeridos")
@router.put("/{estudiante_id}/creditos-requeridos")
def actualizar_creditos_requeridos(
    estudiante_id: int,
    payload: CreditosRequeridosUpdate,
    _user: User = Depends(REQUIERE_ADMIN),
    db: Session = Depends(get_db),
):
    estudiante = db.get(User, estudiante_id)
    if estudiante is None or estudiante.rol != ROL_ESTUDIANTE or estudiante.estudiante is None:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado.")

    estudiante.estudiante.creditos_requeridos = float(payload.creditos_requeridos)
    db.commit()
    db.refresh(estudiante)
    return {
        "id": estudiante.id,
        "email": estudiante.email,
        "nombre": estudiante.nombre,
        "apellido": estudiante.apellido,
        "carrera_id": estudiante.carrera_id,
        "creditos_requeridos": estudiante.estudiante.creditos_requeridos,
    }
