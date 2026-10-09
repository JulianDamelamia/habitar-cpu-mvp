"""Support multiple activity instructors and half-point credits."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261009_docentes_creditos"
down_revision: Union[str, Sequence[str], None] = "20261008_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "docentes" not in tables:
        op.create_table(
            "docentes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nombre", sa.String(length=120), nullable=False),
            sa.Column("apellido", sa.String(length=120), nullable=False),
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "actividad_docente" not in tables:
        op.create_table(
            "actividad_docente",
            sa.Column(
                "actividad_id",
                sa.Integer(),
                sa.ForeignKey("actividades.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "docente_id",
                sa.Integer(),
                sa.ForeignKey("docentes.id", ondelete="CASCADE"),
                primary_key=True,
            ),
        )

    user_columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "docente_id" not in user_columns:
        docente_id_column = sa.Column("docente_id", sa.Integer(), nullable=True)
        if bind.dialect.name != "sqlite":
            docente_id_column.append_foreign_key(sa.ForeignKey("docentes.id"))
        op.add_column("users", docente_id_column)

    activity_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("actividades")
    }
    has_legacy_assignment = "docente_id" in activity_columns

    legacy_filter = "rol != 'estudiante'"
    if has_legacy_assignment:
        legacy_filter += " OR id IN (SELECT docente_id FROM actividades WHERE docente_id IS NOT NULL)"

    bind.execute(
        sa.text(
            f"""
            INSERT INTO docentes (nombre, apellido)
            SELECT MIN(nombre), MIN(apellido)
            FROM users
            WHERE {legacy_filter}
            GROUP BY lower(trim(nombre)), lower(trim(apellido))
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE users
            SET docente_id = (
                SELECT d.id FROM docentes d
                WHERE lower(trim(d.nombre)) = lower(trim(users.nombre))
                  AND lower(trim(d.apellido)) = lower(trim(users.apellido))
            )
            WHERE rol != 'estudiante'
            """
        )
    )

    if has_legacy_assignment:
        bind.execute(
            sa.text(
                """
                INSERT INTO actividad_docente (actividad_id, docente_id)
                SELECT a.id, d.id
                FROM actividades a
                JOIN users u ON u.id = a.docente_id
                JOIN docentes d
                  ON lower(trim(d.nombre)) = lower(trim(u.nombre))
                 AND lower(trim(d.apellido)) = lower(trim(u.apellido))
                WHERE a.docente_id IS NOT NULL
                """
            )
        )

    if bind.dialect.name == "postgresql":
        op.alter_column(
            "actividades",
            "creditos",
            existing_type=sa.Integer(),
            type_=sa.Numeric(8, 2),
            existing_nullable=False,
            postgresql_using="creditos::numeric(8,2)",
        )
        op.create_check_constraint(
            "ck_actividades_creditos_positivo_multiplo_medio",
            "actividades",
            "creditos > 0 AND creditos * 2 = trunc(creditos * 2)",
        )
    elif bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS ck_actividades_creditos_insert
                BEFORE INSERT ON actividades
                WHEN NEW.creditos <= 0
                  OR NEW.creditos * 2 != CAST(NEW.creditos * 2 AS INTEGER)
                BEGIN
                    SELECT RAISE(ABORT, 'creditos must be positive and a multiple of 0.5');
                END
                """
            )
        )
        bind.execute(
            sa.text(
                """
                CREATE TRIGGER IF NOT EXISTS ck_actividades_creditos_update
                BEFORE UPDATE OF creditos ON actividades
                WHEN NEW.creditos <= 0
                  OR NEW.creditos * 2 != CAST(NEW.creditos * 2 AS INTEGER)
                BEGIN
                    SELECT RAISE(ABORT, 'creditos must be positive and a multiple of 0.5');
                END
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        bind.execute(sa.text("DROP TRIGGER IF EXISTS ck_actividades_creditos_insert"))
        bind.execute(sa.text("DROP TRIGGER IF EXISTS ck_actividades_creditos_update"))
    elif bind.dialect.name == "postgresql":
        op.drop_constraint(
            "ck_actividades_creditos_positivo_multiplo_medio",
            "actividades",
            type_="check",
        )
        op.alter_column(
            "actividades",
            "creditos",
            existing_type=sa.Numeric(8, 2),
            type_=sa.Integer(),
            existing_nullable=False,
            postgresql_using="round(creditos)::integer",
        )

    op.drop_table("actividad_docente")
    if "docente_id" in {
        column["name"] for column in sa.inspect(bind).get_columns("users")
    }:
        op.drop_column("users", "docente_id")
    op.drop_table("docentes")
