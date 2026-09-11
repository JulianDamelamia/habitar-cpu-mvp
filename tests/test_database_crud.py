from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from app.database import SessionLocal, engine
from app.models.models import User


@pytest.fixture
def database_session():
    created_users_table = not inspect(engine).has_table(User.__tablename__)
    User.__table__.create(bind=engine, checkfirst=True)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        if created_users_table:
            User.__table__.drop(bind=engine, checkfirst=True)


def test_user_crud(database_session):
    email = f"test-{uuid4().hex}@example.com"
    user = User(
        email=email,
        pw_hash="test-hash",
        nombre="Usuario",
        apellido="De Prueba",
    )
    database_session.add(user)
    database_session.commit()

    created = database_session.get(User, user.id)
    assert created is not None
    assert created.email == email

    created.nombre = "Usuario Actualizado"
    database_session.commit()

    updated = database_session.scalar(select(User).where(User.id == user.id))
    assert updated is not None
    assert updated.nombre == "Usuario Actualizado"

    database_session.delete(updated)
    database_session.commit()
    assert database_session.get(User, user.id) is None