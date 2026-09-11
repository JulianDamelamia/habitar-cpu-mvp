import pytest

from app.models.models import Carrera
from app.services.carreras import (
    add_carrera,
    get_carreras,
    obtener_y_validar_tipo_id,
    resolver_carreras_desde_input,
)


def test_obtener_tipo_id_por_nombre(db_session):
    assert obtener_y_validar_tipo_id(db_session, tipo="Grado") == 1


def test_obtener_tipo_id_por_nombre_ignora_mayusculas_y_espacios(db_session):
    assert obtener_y_validar_tipo_id(db_session, tipo="  gRaDo  ") == 1


def test_obtener_tipo_id_por_id(db_session):
    assert obtener_y_validar_tipo_id(db_session, tipo_id=2) == 2


def test_obtener_tipo_id_valida_nombre_e_id_coincidentes(db_session):
    assert obtener_y_validar_tipo_id(db_session, tipo="Posgrado", tipo_id=2) == 2


@pytest.mark.parametrize(
    "kwargs, mensaje",
    [
        ({}, "Debe proporcionar"),
        ({"tipo": "Inexistente"}, "no existe"),
        ({"tipo_id": 99}, "no existe"),
        (
            {"tipo": "Grado", "tipo_id": 2},
            "Inconsistencia",
        ),
    ],
)
def test_obtener_tipo_id_rechaza_argumentos_invalidos(db_session, kwargs, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        obtener_y_validar_tipo_id(db_session, **kwargs)


def test_add_carrera_crea_y_persiste_la_carrera(db_session):
    carrera = add_carrera(db_session, "Arquitectura", tipo_id=1)

    assert isinstance(carrera, Carrera)
    assert carrera.id is not None
    assert carrera.nombre == "Arquitectura"
    assert carrera.tipo_id == 1
    assert carrera.tipo.nombre == "Grado"
    assert db_session.get(Carrera, carrera.id) == carrera


def test_add_carrera_acepta_tipo_por_nombre(db_session):
    carrera = add_carrera(db_session, "Diseño", tipo="Posgrado")

    assert carrera.tipo_id == 2
    assert carrera.tipo.nombre == "Posgrado"


def test_get_carreras_ordena_por_tipo_y_luego_por_nombre(db_session):
    add_carrera(db_session, "Zoología", tipo_id=1)
    add_carrera(db_session, "Arquitectura", tipo_id=1)
    add_carrera(db_session, "Biología", tipo_id=2)

    carreras = get_carreras(db_session)

    assert [(carrera.tipo.nombre, carrera.nombre) for carrera in carreras] == [
        ("Grado", "Arquitectura"),
        ("Grado", "Zoología"),
        ("Posgrado", "Biología"),
    ]
    assert all(carrera.tipo is not None for carrera in carreras)


def test_resolver_carreras_devuelve_lista_vacia_sin_entrada(db_session):
    assert resolver_carreras_desde_input([], db_session) == []


def test_resolver_carreras_resuelve_ids(db_session):
    arquitectura = add_carrera(db_session, "Arquitectura", tipo_id=1)
    diseño = add_carrera(db_session, "Diseño", tipo_id=2)

    carreras = resolver_carreras_desde_input(
        [str(diseño.id), str(arquitectura.id)], db_session
    )

    assert {carrera.id for carrera in carreras} == {arquitectura.id, diseño.id}


def test_resolver_carreras_con_todas_devuelve_todas(db_session):
    arquitectura = add_carrera(db_session, "Arquitectura", tipo_id=1)
    diseño = add_carrera(db_session, "Diseño", tipo_id=2)

    carreras = resolver_carreras_desde_input(["todas"], db_session)

    assert {carrera.id for carrera in carreras} == {arquitectura.id, diseño.id}


def test_resolver_carreras_ignora_valores_no_numericos(db_session):
    carrera = add_carrera(db_session, "Arquitectura", tipo_id=1)

    carreras = resolver_carreras_desde_input(["no-es-un-id", str(carrera.id)], db_session)

    assert carreras == [carrera]


def test_resolver_carreras_rechaza_ids_inexistentes(db_session):
    with pytest.raises(ValueError, match="no existen"):
        resolver_carreras_desde_input(["999"], db_session)