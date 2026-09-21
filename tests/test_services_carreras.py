import pytest

from app.models import Carrera
from app.services.carreras import (
    add,
    get_carreras,
    _obtener_y_validar_tipo_id,
    get_carreras_desde_dropdown,
    update,
)


def test_obtener_tipo_id_por_nombre(db_session):
    assert _obtener_y_validar_tipo_id(db_session, tipo="Grado") == 1


def test_obtener_tipo_id_por_nombre_ignora_mayusculas_y_espacios(db_session):
    assert _obtener_y_validar_tipo_id(db_session, tipo="  gRaDo  ") == 1


def test_obtener_tipo_id_por_id(db_session):
    assert _obtener_y_validar_tipo_id(db_session, tipo_id=2) == 2


def test_obtener_tipo_id_valida_nombre_e_id_coincidentes(db_session):
    assert _obtener_y_validar_tipo_id(db_session, tipo="Posgrado", tipo_id=2) == 2


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
        _obtener_y_validar_tipo_id(db_session, **kwargs)


def test_add_crea_y_persiste_la_carrera(db_session):
    carrera = add(db_session, "Arquitectura", creditos_requeridos=12, tipo_id=1)

    assert isinstance(carrera, Carrera)
    assert carrera.id is not None
    assert carrera.nombre == "Arquitectura"
    assert carrera.tipo_id == 1
    assert carrera.creditos_requeridos == 12
    assert carrera.tipo.nombre == "Grado"
    assert db_session.get(Carrera, carrera.id) == carrera


def test_add_acepta_tipo_por_nombre(db_session):
    carrera = add(db_session, "Diseño", creditos_requeridos=15, tipo="Posgrado")

    assert carrera.tipo_id == 2
    assert carrera.tipo.nombre == "Posgrado"


def test_add_rechaza_combinacion_tipo_y_nombre_duplicada_sin_distinguir_mayusculas(
    db_session,
):
    add(db_session, "Arquitectura", creditos_requeridos=12, tipo="Grado")

    with pytest.raises(ValueError, match="ya existe"):
        add(db_session, " arquitectura ", creditos_requeridos=18, tipo="gRaDo")


def test_update_actualiza_atributos_y_permite_conservar_la_misma_carrera(db_session):
    carrera = add(db_session, "Arquitectura", creditos_requeridos=12, tipo_id=1)

    update(db_session, carrera, " Arquitectura ", creditos_requeridos=18, tipo_id=1)

    assert carrera.nombre == "Arquitectura"
    assert carrera.creditos_requeridos == 18


def test_update_rechaza_combinacion_duplicada_sin_distinguir_mayusculas(db_session):
    add(db_session, "Arquitectura", creditos_requeridos=12, tipo_id=1)
    otra = add(db_session, "Diseño", creditos_requeridos=15, tipo_id=1)

    with pytest.raises(ValueError, match="ya existe"):
        update(db_session, otra, " ARQUITECTURA ", creditos_requeridos=18, tipo_id=1)


def test_add_rechaza_creditos_requeridos_invalidos(db_session):
    with pytest.raises(ValueError, match="mayores que cero"):
        add(db_session, "Arquitectura", creditos_requeridos=0, tipo_id=1)


def test_get_carreras_ordena_por_tipo_y_luego_por_nombre(db_session):
    add(db_session, "Zoología", creditos_requeridos=10, tipo_id=1)
    add(db_session, "Arquitectura", creditos_requeridos=10, tipo_id=1)
    add(db_session, "Biología", creditos_requeridos=10, tipo_id=2)

    carreras = get_carreras(db_session)

    assert [(carrera.tipo.nombre, carrera.nombre) for carrera in carreras] == [
        ("Grado", "Arquitectura"),
        ("Grado", "Zoología"),
        ("Posgrado", "Biología"),
    ]
    assert all(carrera.tipo is not None for carrera in carreras)


def test_resolver_carreras_devuelve_lista_vacia_sin_entrada(db_session):
    assert get_carreras_desde_dropdown([], db_session) == []


def test_resolver_carreras_resuelve_ids(db_session):
    arquitectura = add(db_session, "Arquitectura", creditos_requeridos=10, tipo_id=1)
    diseño = add(db_session, "Diseño", creditos_requeridos=15, tipo_id=2)

    carreras = get_carreras_desde_dropdown(
        [str(diseño.id), str(arquitectura.id)], db_session
    )

    assert {carrera.id for carrera in carreras} == {arquitectura.id, diseño.id}


def test_resolver_carreras_con_todas_devuelve_todas(db_session):
    arquitectura = add(db_session, "Arquitectura", creditos_requeridos=10, tipo_id=1)
    diseño = add(db_session, "Diseño", creditos_requeridos=15, tipo_id=2)

    carreras = get_carreras_desde_dropdown(["todas"], db_session)

    assert {carrera.id for carrera in carreras} == {arquitectura.id, diseño.id}


def test_resolver_carreras_ignora_valores_no_numericos(db_session):
    carrera = add(db_session, "Arquitectura", creditos_requeridos=10, tipo_id=1)

    carreras = get_carreras_desde_dropdown(["no-es-un-id", str(carrera.id)], db_session)

    assert carreras == [carrera]


def test_resolver_carreras_rechaza_ids_inexistentes(db_session):
    with pytest.raises(ValueError, match="no existen"):
        get_carreras_desde_dropdown(["999"], db_session)