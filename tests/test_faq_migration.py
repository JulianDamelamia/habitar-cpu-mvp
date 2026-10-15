from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_faq_categories_migration_preserves_existing_rows_and_reverses():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "20261015_faq_categories.py"
    )
    spec = spec_from_file_location("faq_categories_migration", migration_path)
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE faq (
                id INTEGER PRIMARY KEY,
                pregunta VARCHAR(300) NOT NULL,
                respuesta TEXT NOT NULL,
                orden INTEGER NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO faq (pregunta, respuesta, orden) VALUES ('Pregunta', 'Respuesta', 7)"
        )
        connection.exec_driver_sql(
            """
            CREATE TABLE faq_categorias (
                id INTEGER PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL UNIQUE
            )
            """
        )
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        faq_columns = {column["name"] for column in inspect(connection).get_columns("faq")}
        assert "orden" not in faq_columns
        assert "categoria_id" in faq_columns
        assert connection.execute(
            text(
                """
                SELECT faq.pregunta, faq.respuesta, faq.categoria_id, faq_categorias.nombre
                FROM faq JOIN faq_categorias ON faq.categoria_id = faq_categorias.id
                WHERE faq.id = 1
                """
            )
        ).one() == ("Pregunta", "Respuesta", 1, "General")

        with Operations.context(context):
            migration.downgrade()

        faq_columns = {column["name"] for column in inspect(connection).get_columns("faq")}
        assert "orden" in faq_columns
        assert "categoria_id" not in faq_columns
        assert connection.execute(text("SELECT orden FROM faq WHERE id = 1")).scalar_one() == 0
        assert "faq_categorias" not in inspect(connection).get_table_names()

    engine.dispose()
