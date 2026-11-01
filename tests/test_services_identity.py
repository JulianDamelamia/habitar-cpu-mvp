import pytest

from app.models import Persona, User
from app.security import hash_password
from app.services.identity import (
    SignupContext,
    SignupError,
    authenticate,
    create_student,
    email_taken,
)


def test_create_student_rechaza_email_repetido(db_session):
    db_session.add(
        User(
            persona=Persona(
                email="existente@example.com",
                nombre="Existente",
                apellido="Usuario",
            ),
            pw_hash="hash",
        )
    )
    db_session.commit()

    with pytest.raises(SignupError, match="Ya existe"):
        create_student(
            db_session,
            SignupContext(
                email="existente@example.com",
                password="secret",
                nombre="Nuevo",
                apellido="Usuario",
                carrera_id=None,
            ),
        )


def test_email_taken_y_authenticate_normalizan_email(db_session):
    user = User(
        persona=Persona(
            email="alumno@example.com",
            nombre="Alumno",
            apellido="Prueba",
        ),
        pw_hash=hash_password("secret"),
    )
    db_session.add(user)
    db_session.commit()

    assert email_taken(db_session, " ALUMNO@EXAMPLE.COM ")
    assert authenticate(db_session, " ALUMNO@EXAMPLE.COM ", "secret") == user
    assert authenticate(db_session, "alumno@example.com", "incorrecta") is None
    assert authenticate(db_session, "otro@example.com", "secret") is None
