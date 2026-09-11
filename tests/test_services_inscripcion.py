import pytest

from app.models import ESTADO_PUBLICADA, INSCRIPCION_ALTA, Inscripcion
from app.services.inscripcion import (
    EnrollError,
    active_enrollment,
    inscribir,
    inscriptos,
    is_enrolled,
    my_actividades,
    unenroll,
)


def test_inscribir_y_consultar_inscripcion(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()

    resultado = inscribir(db_session, actividad.id, usuario.id)

    assert resultado.id == actividad.id
    assert is_enrolled(db_session, actividad.id, usuario.id)
    assert active_enrollment(db_session, actividad.id, usuario.id).estado == INSCRIPCION_ALTA
    assert [e.user_id for e in inscriptos(db_session, actividad.id)] == [usuario.id]


@pytest.mark.parametrize(
    "actividad_id, estado, mensaje",
    [(9999, None, "no existe"), (None, "borrador", "no está disponible")],
)
def test_inscribir_rechaza_actividad_invalida(
    db_session, actividad_factory, user_factory, actividad_id, estado, mensaje
):
    usuario = user_factory()
    if estado:
        actividad_id = actividad_factory(estado=estado).id

    with pytest.raises(EnrollError, match=mensaje):
        inscribir(db_session, actividad_id, usuario.id)


def test_inscribir_rechaza_duplicado_y_cupo_lleno(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA, cupo_max=1)
    primero = user_factory()
    segundo = user_factory()
    inscribir(db_session, actividad.id, primero.id)

    with pytest.raises(EnrollError, match="Ya estás inscripto"):
        inscribir(db_session, actividad.id, primero.id)
    with pytest.raises(EnrollError, match="No quedan cupos"):
        inscribir(db_session, actividad.id, segundo.id)


def test_unenroll_permite_reinscripcion(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()
    inscribir(db_session, actividad.id, usuario.id)

    unenroll(db_session, actividad.id, usuario.id)
    assert not is_enrolled(db_session, actividad.id, usuario.id)
    assert db_session.query(Inscripcion).filter_by(actividad_id=actividad.id).one().estado != INSCRIPCION_ALTA
    inscribir(db_session, actividad.id, usuario.id)
    assert is_enrolled(db_session, actividad.id, usuario.id)


def test_unenroll_sin_inscripcion_falla(db_session, actividad_factory, user_factory):
    actividad = actividad_factory(estado=ESTADO_PUBLICADA)
    usuario = user_factory()

    with pytest.raises(EnrollError, match="No estás inscripto"):
        unenroll(db_session, actividad.id, usuario.id)


def test_my_actividades_filtra_publicadas_y_ordena(db_session, actividad_factory, user_factory):
    usuario = user_factory()
    futura = actividad_factory(estado=ESTADO_PUBLICADA)
    borrador = actividad_factory(estado="borrador")
    inscribir(db_session, futura.id, usuario.id)
    db_session.add(
        Inscripcion(actividad_id=borrador.id, user_id=usuario.id, estado=INSCRIPCION_ALTA)
    )
    db_session.commit()

    assert my_actividades(db_session, usuario.id) == [futura]