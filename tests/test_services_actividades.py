from datetime import datetime, timedelta, timezone

from app.models import ESTADO_PUBLICADA, Inscripcion
from app.services.actividades import (
    create,
    cupo_info,
    get,
    inscriptos_count,
    list_all,
    list_published,
    update,
)


def test_get_devuelve_actividad_o_none(db_session, actividad_factory):
    actividad = actividad_factory()

    assert get(db_session, actividad.id) == actividad
    assert get(db_session, 9999) is None


def test_inscriptos_count_y_cupo_info_cuentan_solo_inscripciones_activas(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(cupo_max=2)
    activos = [user_factory(), user_factory()]
    db_session.add_all(
        [
            Inscripcion(actividad_id=actividad.id, user_id=activos[0].id, estado="inscripto"),
            Inscripcion(actividad_id=actividad.id, user_id=activos[1].id, estado="baja"),
        ]
    )
    db_session.commit()

    assert inscriptos_count(db_session, actividad.id) == 1
    assert cupo_info(db_session, actividad) == {"taken": 1, "free": 1, "full": False}


def test_cupo_info_no_informa_cupos_negativos(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(cupo_max=1)
    usuario = user_factory()
    db_session.add(Inscripcion(actividad_id=actividad.id, user_id=usuario.id))
    db_session.commit()

    assert cupo_info(db_session, actividad) == {"taken": 1, "free": 0, "full": True}


def test_list_published_aplica_filtros_y_ordena(db_session, actividad_factory, carrera_factory):
    carrera = carrera_factory()
    base = datetime(2026, 9, 20, tzinfo=timezone.utc)
    actividad_factory(
        titulo="Taller virtual",
        fecha_inicio=base + timedelta(hours=2),
        estado=ESTADO_PUBLICADA,
        tipo="virtual",
        creditos=4,
        carreras=[carrera],
    )
    esperada = actividad_factory(
        titulo="Taller presencial",
        fecha_inicio=base,
        estado=ESTADO_PUBLICADA,
        tipo="presencial",
        creditos=3,
        carreras=[carrera],
    )
    actividad_factory(titulo="Borrador", fecha_inicio=base, carreras=[carrera])

    resultado = list_published(
        db_session,
        carreras_ids=[carrera.id],
        tipo="presencial",
        fecha="2026-09-20",
        min_creditos=3,
    )

    assert resultado == [esperada]


def test_list_published_devuelve_vacio_para_estudiante_sin_carreras(db_session):
    assert list_published(db_session, carreras_ids=[]) == []


def test_list_published_solo_disponibles_excluye_llenas(
    db_session, actividad_factory, user_factory
):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA, cupo_max=1)
    usuario = user_factory()
    db_session.add(Inscripcion(actividad_id=actividad.id, user_id=usuario.id))
    db_session.commit()

    assert list_published(db_session, solo_disponibles=True) == []


def test_list_all_filtra_carreras_y_acepta_todas(db_session, actividad_factory, carrera_factory):
    arquitectura = carrera_factory()
    diseno = carrera_factory(nombre="Diseño")
    con_carrera = actividad_factory(carreras=[arquitectura])
    sin_carrera = actividad_factory(carreras=[diseno])

    assert list_all(db_session, carreras_ids=[str(arquitectura.id)]) == [con_carrera]
    assert {a.id for a in list_all(db_session, carreras_ids=["todas"])} == {
        con_carrera.id,
        sin_carrera.id,
    }


def test_create_y_update_persisten_actividad(db_session, actividad_factory):
    actividad = create(
        db_session,
        titulo="Nueva actividad",
        fecha_inicio=datetime(2026, 10, 1),
        fecha_fin=datetime(2026, 10, 1, 2),
        estado=ESTADO_PUBLICADA,
    )
    update(db_session, actividad, titulo="Actividad actualizada", creditos=5)

    assert get(db_session, actividad.id).titulo == "Actividad actualizada"
    assert get(db_session, actividad.id).creditos == 5