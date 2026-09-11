from app.models import ROL_COORDINACION
from app.seed import DEMO_PASSWORD, _get_or_create_user
from app.security import hash_password, verify_password


def test_get_or_create_demo_user_repairs_an_old_password_hash(db_session):
    user = _get_or_create_user(
        db_session,
        "ana@alumno.unsam.edu.ar",
        nombre="Ana",
        apellido="Pérez",
        rol=ROL_COORDINACION,
    )
    user.pw_hash = hash_password("otra-password")
    db_session.commit()

    _get_or_create_user(
        db_session,
        "ana@alumno.unsam.edu.ar",
        nombre="Ana",
        apellido="Pérez",
        rol=ROL_COORDINACION,
    )
    db_session.commit()

    assert verify_password(DEMO_PASSWORD, user.pw_hash)