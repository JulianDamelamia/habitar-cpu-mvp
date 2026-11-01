from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def _migration():
    path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20261101_user_persona_required.py"
    )
    spec = spec_from_file_location("user_persona_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_upgrade_deletes_users_without_email_and_their_dependent_rows():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE personas (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                email TEXT NULL
            )
            """
        )
        connection.exec_driver_sql("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                persona_id INTEGER NULL,
                rol TEXT
            )
        """)
        connection.exec_driver_sql("""
            CREATE TABLE user_records (
                id INTEGER PRIMARY KEY,
                owner_id INTEGER NOT NULL REFERENCES users(id),
                actor_id INTEGER NULL REFERENCES users(id)
            )
        """)
        connection.exec_driver_sql(
            "INSERT INTO personas VALUES (1, 'Sin', 'Email', NULL)"
        )
        connection.exec_driver_sql("INSERT INTO users VALUES (1, 1, 'estudiante')")
        connection.exec_driver_sql("INSERT INTO user_records VALUES (1, 1, 1)")

        with Operations.context(MigrationContext.configure(connection)):
            _migration().upgrade()

        assert connection.exec_driver_sql("SELECT COUNT(*) FROM users").scalar_one() == 0
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM user_records"
        ).scalar_one() == 0
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM personas"
        ).scalar_one() == 1
    engine.dispose()


def test_upgrade_makes_persona_reference_required_and_unique():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE personas (
                id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL,
                email TEXT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                persona_id INTEGER NULL,
                rol TEXT
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE docentes (
                id INTEGER PRIMARY KEY,
                persona_id INTEGER NULL,
                nombre TEXT NOT NULL,
                apellido TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO personas VALUES (1, 'Otro', 'Registro', NULL)"
        )
        connection.exec_driver_sql("INSERT INTO personas VALUES (2, 'Eva', 'Docente', 'eva@example.com')")
        connection.exec_driver_sql("INSERT INTO users VALUES (1, 2, 'docente')")
        connection.exec_driver_sql("INSERT INTO docentes VALUES (1, NULL, 'Eva', 'Docente')")

        with Operations.context(MigrationContext.configure(connection)):
            _migration().upgrade()

        persona_id = inspect(connection).get_columns("users")[1]
        assert persona_id["nullable"] is False
        assert any(
            constraint["column_names"] == ["persona_id"]
            for constraint in inspect(connection).get_unique_constraints("users")
        )
        docente_persona_id = connection.exec_driver_sql(
            "SELECT persona_id FROM docentes WHERE id = 1"
        ).scalar_one()
        assert docente_persona_id == 2
        assert inspect(connection).get_columns("docentes")[1]["nullable"] is True
        assert any(
            constraint["column_names"] == ["persona_id"]
            for constraint in inspect(connection).get_unique_constraints("docentes")
        )
    engine.dispose()
