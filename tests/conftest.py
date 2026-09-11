import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.models import (
    Actividad,
    Carrera,
    ESTADO_BORRADOR,
    TipoCarrera,
    User,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                TipoCarrera(id=1, nombre="Grado"),
                TipoCarrera(id=2, nombre="Posgrado"),
            ]
        )
        session.commit()
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def user_factory(db_session):
    counter = 0

    def create_user(*, rol="estudiante", email=None):
        nonlocal counter
        counter += 1
        user = User(
            email=email or f"user-{counter}@example.com",
            pw_hash="test-hash",
            nombre=f"Nombre {counter}",
            apellido="Prueba",
            rol=rol,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return create_user


@pytest.fixture
def carrera_factory(db_session):
    def create_carrera(nombre="Arquitectura", tipo_id=1):
        carrera = Carrera(nombre=nombre, tipo_id=tipo_id)
        db_session.add(carrera)
        db_session.commit()
        db_session.refresh(carrera)
        return carrera

    return create_carrera


@pytest.fixture
def actividad_factory(db_session):
    counter = 0

    def create_actividad(
        *,
        titulo=None,
        fecha_inicio=None,
        estado=ESTADO_BORRADOR,
        creditos=2,
        cupo_max=30,
        tipo="presencial",
        carreras=None,
    ):
        nonlocal counter
        counter += 1
        fecha_inicio = fecha_inicio or datetime.now(timezone.utc) + timedelta(days=counter)
        actividad = Actividad(
            titulo=titulo or f"Actividad {counter}",
            descripcion="Descripción de prueba",
            tipo=tipo,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_inicio + timedelta(hours=2),
            lugar="Campus Miguelete",
            creditos=creditos,
            cupo_max=cupo_max,
            estado=estado,
        )
        if carreras:
            actividad.carreras_asociadas.extend(carreras)
        db_session.add(actividad)
        db_session.commit()
        db_session.refresh(actividad)
        return actividad

    return create_actividad