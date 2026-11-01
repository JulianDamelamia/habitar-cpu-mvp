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
        / "20261102_docente_persona_required.py"
    )
    spec = spec_from_file_location("docente_identity_migration", path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _create_legacy_schema(connection):
    connection.exec_driver_sql(
        """
        CREATE TABLE personas (
            id INTEGER PRIMARY KEY,
            nombre VARCHAR(120) NOT NULL,
            apellido VARCHAR(120) NOT NULL,
            email VARCHAR(120) NOT NULL UNIQUE
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE docentes (
            id INTEGER PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            apellido VARCHAR(100) NOT NULL,
            persona_id INTEGER NULL UNIQUE REFERENCES personas(id)
        )
        """
    )


def test_upgrade_moves_legacy_identity_to_persona_and_requires_link():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        _create_legacy_schema(connection)
        connection.exec_driver_sql(
            "INSERT INTO personas VALUES (1, 'Eva', 'Docente', 'eva@example.com')"
        )
        connection.exec_driver_sql(
            "INSERT INTO docentes VALUES (1, 'Eva', 'Docente', 1)"
        )
        connection.exec_driver_sql(
            "INSERT INTO docentes VALUES (2, 'Ana', 'Invitada', NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO docentes VALUES (3, 'Luis', 'Invitado', NULL)"
        )

        with Operations.context(MigrationContext.configure(connection)):
            _migration().upgrade()

        docente_columns = {
            column["name"]: column
            for column in inspect(connection).get_columns("docentes")
        }
        assert set(docente_columns) == {"id", "persona_id"}
        assert docente_columns["persona_id"]["nullable"] is False
        assert inspect(connection).get_columns("personas")[3]["nullable"] is True
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM docentes WHERE persona_id IS NULL"
        ).scalar_one() == 0
        assert connection.exec_driver_sql(
            """
            SELECT COUNT(*)
            FROM docentes d
            JOIN personas p ON p.id = d.persona_id
            WHERE (d.id = 2 AND p.nombre = 'Ana' AND p.apellido = 'Invitada')
               OR (d.id = 3 AND p.nombre = 'Luis' AND p.apellido = 'Invitado')
            """
        ).scalar_one() == 2
        assert connection.exec_driver_sql(
            "SELECT COUNT(*) FROM personas WHERE email IS NULL"
        ).scalar_one() == 2
    engine.dispose()


def test_downgrade_restores_legacy_names_from_persona():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE personas (
                id INTEGER PRIMARY KEY,
                nombre VARCHAR(120) NOT NULL,
                apellido VARCHAR(120) NOT NULL,
                email VARCHAR(120) NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE docentes (
                id INTEGER PRIMARY KEY,
                persona_id INTEGER NOT NULL UNIQUE REFERENCES personas(id)
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO personas VALUES (1, 'Eva', 'Docente', NULL)"
        )
        connection.exec_driver_sql("INSERT INTO docentes VALUES (1, 1)")

        with Operations.context(MigrationContext.configure(connection)):
            _migration().downgrade()

        docente_columns = {
            column["name"]: column
            for column in inspect(connection).get_columns("docentes")
        }
        assert set(docente_columns) == {"id", "persona_id", "nombre", "apellido"}
        assert docente_columns["persona_id"]["nullable"] is True
        assert connection.exec_driver_sql(
            "SELECT nombre, apellido FROM docentes WHERE id = 1"
        ).one() == ("Eva", "Docente")
    engine.dispose()
