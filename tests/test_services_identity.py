import pytest

from app.models import ROL_ESTUDIANTE, User#, ValidLegajo
from app.models.carrera import Carrera
from app.security import hash_password
from app.services.identity import (
    SignupError,
    authenticate,
    create_student,
    email_taken,

)





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