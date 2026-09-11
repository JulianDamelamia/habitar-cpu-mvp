from app.models import (
    Asistencia,
    ESTADO_PUBLICADA,
    Inscripcion,
    SurveyResponse,
)
from app.services.analytics import (
    asistencia_per_actividad,
    overview,
    survey_averages,
    top_actividades,
)


def test_overview_calcula_totales_y_tasa(db_session, actividad_factory, user_factory):
    publicada = actividad_factory(estado=ESTADO_PUBLICADA)
    actividad_factory(estado="borrador")
    usuario = user_factory()
    db_session.add(Inscripcion(actividad_id=publicada.id, user_id=usuario.id))
    db_session.add(Asistencia(actividad_id=publicada.id, user_id=usuario.id))
    db_session.commit()

    assert overview(db_session) == {
        "actividades_publicadas": 1,
        "inscripciones": 1,
        "asistencias": 1,
        "asistencia_rate": 100.0,
    }


def test_overview_sin_inscripciones_tiene_tasa_cero(db_session, actividad_factory):
    actividad_factory(estado=ESTADO_PUBLICADA)

    assert overview(db_session)["asistencia_rate"] == 0.0


def test_top_actividades_ordena_y_respeta_limite(
    db_session, actividad_factory, user_factory
):
    primera = actividad_factory(titulo="Primera")
    segunda = actividad_factory(titulo="Segunda")
    usuarios = [user_factory() for _ in range(3)]
    db_session.add_all(
        [
            Inscripcion(actividad_id=primera.id, user_id=usuarios[0].id),
            Inscripcion(actividad_id=primera.id, user_id=usuarios[1].id),
            Inscripcion(actividad_id=segunda.id, user_id=usuarios[2].id),
        ]
    )
    db_session.commit()

    assert top_actividades(db_session, limit=1) == [{"titulo": "Primera", "inscriptos": 2}]


def test_asistencia_per_actividad_omite_sin_inscriptos_y_calcula_rate(
    db_session, actividad_factory, user_factory
):
    con_datos = actividad_factory(titulo="Con datos", estado=ESTADO_PUBLICADA)
    actividad_factory(titulo="Sin datos", estado=ESTADO_PUBLICADA)
    usuarios = [user_factory() for _ in range(2)]
    db_session.add_all(
        [
            Inscripcion(actividad_id=con_datos.id, user_id=usuarios[0].id),
            Inscripcion(actividad_id=con_datos.id, user_id=usuarios[1].id),
            Asistencia(actividad_id=con_datos.id, user_id=usuarios[0].id),
        ]
    )
    db_session.commit()

    assert asistencia_per_actividad(db_session) == [
        {"titulo": "Con datos", "inscriptos": 2, "asistencias": 1, "rate": 50.0}
    ]


def test_survey_averages_ordena_y_redondea(db_session, actividad_factory, user_factory):
    mejor = actividad_factory(titulo="Mejor")
    otra = actividad_factory(titulo="Otra")
    usuarios = [user_factory() for _ in range(3)]
    db_session.add_all(
        [
            SurveyResponse(actividad_id=mejor.id, user_id=usuarios[0].id, rating=5),
            SurveyResponse(actividad_id=mejor.id, user_id=usuarios[1].id, rating=4),
            SurveyResponse(actividad_id=otra.id, user_id=usuarios[2].id, rating=3),
        ]
    )
    db_session.commit()

    assert survey_averages(db_session) == [
        {"titulo": "Mejor", "promedio": 4.5, "respuestas": 2},
        {"titulo": "Otra", "promedio": 3.0, "respuestas": 1},
    ]