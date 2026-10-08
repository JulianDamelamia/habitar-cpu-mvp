from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
import pytest


@pytest.mark.parametrize("student_table_exists", [False, True])
def test_upgrade_moves_existing_student_career_and_credits(student_table_exists):
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20261008_estudiante_creditos.py"
    )
    spec = spec_from_file_location("student_credits_migration", migration_path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, rol TEXT, carrera_id INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE carreras (id INTEGER PRIMARY KEY, creditos_requeridos INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE actividades (id INTEGER PRIMARY KEY, creditos INTEGER)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE asistencia (user_id INTEGER, actividad_id INTEGER)"
        )
        connection.exec_driver_sql(
            "INSERT INTO users VALUES "
            "(1, 'estudiante', 3), (2, 'docente', NULL), (3, 'estudiante', NULL)"
        )
        connection.exec_driver_sql("INSERT INTO carreras VALUES (3, 12)")
        connection.exec_driver_sql("INSERT INTO actividades VALUES (5, 2), (6, 3)")
        connection.exec_driver_sql(
            "INSERT INTO asistencia VALUES (1, 5), (1, 6)"
        )
        if student_table_exists:
            connection.exec_driver_sql(
                """
                CREATE TABLE estudiantes (
                    user_id INTEGER PRIMARY KEY,
                    carrera_id INTEGER,
                    creditos_acreditados FLOAT NOT NULL DEFAULT 0,
                    creditos_requeridos FLOAT NOT NULL DEFAULT 10,
                    creditos_penalizacion FLOAT NOT NULL DEFAULT 0
                )
                """
            )

        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        student = connection.execute(
            text("SELECT * FROM estudiantes WHERE user_id = 1")
        ).one()
        assert student.carrera_id == 3
        assert student.creditos_acreditados == 5
        assert student.creditos_requeridos == 12
        assert student.creditos_penalizacion == 0
        student_without_career = connection.execute(
            text("SELECT * FROM estudiantes WHERE user_id = 3")
        ).one()
        assert student_without_career.carrera_id is None
        assert student_without_career.creditos_requeridos == 10
        assert "carrera_id" not in {
            column["name"] for column in inspect(connection).get_columns("users")
        }
        assert connection.execute(text("SELECT COUNT(*) FROM estudiantes")).scalar_one() == 2

    engine.dispose()
