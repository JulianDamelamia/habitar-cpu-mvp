import pytest

from app.models.models import ROL_ESTUDIANTE, User, ValidLegajo
from app.security import hash_password
from app.services.identity import (
    SignupError,
    authenticate,
    create_student,
    email_taken,
    legajo_is_valid,
)


def test_legajo_is_valid_recorta_espacios(db_session):
    db_session.add(ValidLegajo(legajo="1234", nombre="Estudiante"))
    db_session.commit()

    assert legajo_is_valid(db_session, " 1234 ")
    assert not legajo_is_valid(db_session, "9999")


def test_create_student_normaliza_datos_y_persiste(db_session):
    db_session.add(ValidLegajo(legajo="1234", nombre="Estudiante"))
    db_session.commit()

    user = create_student(
        db_session,
        legajo=" 1234 ",
        email="  ALUMNO@EXAMPLE.COM ",
        password="secret",
        nombre="  Ana ",
        apellido=" Pérez ",
        dni=" 30123456 ",
        carrera="Arquitectura",
    )

    assert user.email == "alumno@example.com"
    assert user.nombre == "Ana"
    assert user.apellido == "Pérez"
    assert user.dni == "30123456"
    assert user.rol == ROL_ESTUDIANTE
    assert db_session.get(User, user.id) == user


@pytest.mark.parametrize(
    "kwargs, mensaje",
    [
        ({"legajo": "9999", "email": "nuevo@example.com"}, "no figura"),
        ({"legajo": "1234", "email": "existente@example.com"}, "Ya existe"),
    ],
)
def test_create_student_rechaza_legajo_invalido_o_email_repetido(
    db_session, kwargs, mensaje
):
    db_session.add(ValidLegajo(legajo="1234", nombre="Estudiante"))
    db_session.add(User(email="existente@example.com", pw_hash="hash"))
    db_session.commit()
    kwargs = {
        "password": "secret",
        "nombre": "Nuevo",
        "apellido": "Usuario",
        "dni": None,
        "carrera": None,
        **kwargs,
    }

    with pytest.raises(SignupError, match=mensaje):
        create_student(db_session, **kwargs)


def test_email_taken_y_authenticate_normalizan_email(db_session, user_factory):
    user = User(email="alumno@example.com", pw_hash=hash_password("secret"))
    db_session.add(user)
    db_session.commit()

    assert email_taken(db_session, " ALUMNO@EXAMPLE.COM ")
    assert authenticate(db_session, " ALUMNO@EXAMPLE.COM ", "secret") == user
    assert authenticate(db_session, "alumno@example.com", "incorrecta") is None
    assert authenticate(db_session, "otro@example.com", "secret") is None