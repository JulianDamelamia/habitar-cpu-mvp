"""Move career to student profile and add per-student credits.

Revision ID: 20261008_estudiante
Revises: 20261007_debe_cambiar_pw
Create Date: 2026-10-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261008_estudiante"
down_revision: Union[str, Sequence[str], None] = "20261007_debe_cambiar_pw"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "estudiantes" not in tables:
        op.create_table(
            "estudiantes",
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "carrera_id",
                sa.Integer(),
                sa.ForeignKey("carreras.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "creditos_acreditados",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "creditos_requeridos",
                sa.Float(),
                nullable=False,
                server_default=sa.text("10"),
            ),
            sa.Column(
                "creditos_penalizacion",
                sa.Float(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.CheckConstraint(
                "creditos_acreditados >= 0",
                name="ck_estudiante_creditos_acreditados",
            ),
            sa.CheckConstraint(
                "creditos_requeridos > 0",
                name="ck_estudiante_creditos_requeridos",
            ),
            sa.CheckConstraint(
                "creditos_penalizacion >= 0",
                name="ck_estudiante_creditos_penalizacion",
            ),
        )
        op.create_index(
            "ix_estudiantes_carrera_id", "estudiantes", ["carrera_id"]
        )

    user_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("users")
    }
    if "carrera_id" not in user_columns:
        return

    if "asistencia" in tables and "actividades" in tables:
        credited = """
            COALESCE(SUM(actividades.creditos), 0)
        """
        attendance_join = """
            LEFT JOIN asistencia ON asistencia.user_id = users.id
            LEFT JOIN actividades ON actividades.id = asistencia.actividad_id
        """
    else:
        credited = "0"
        attendance_join = ""

    required = (
        "COALESCE(carreras.creditos_requeridos, 10)"
        if "carreras" in tables
        else "10"
    )
    career_join = (
        "LEFT JOIN carreras ON carreras.id = users.carrera_id"
        if "carreras" in tables
        else ""
    )
    group_by = (
        "GROUP BY users.id, users.carrera_id, carreras.creditos_requeridos"
        if "carreras" in tables
        else "GROUP BY users.id, users.carrera_id"
    )
    op.execute(
        sa.text(
            f"""
            INSERT INTO estudiantes (
                user_id, carrera_id, creditos_acreditados,
                creditos_requeridos, creditos_penalizacion
            )
            SELECT users.id, users.carrera_id, {credited}, {required}, 0
            FROM users
            {career_join}
            {attendance_join}
            WHERE users.rol = 'estudiante'
            {group_by}
            ON CONFLICT (user_id) DO NOTHING
            """
        )
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("carrera_id")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("carrera_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_carrera_id_carreras",
            "carreras",
            ["carrera_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET carrera_id = (
                SELECT estudiantes.carrera_id
                FROM estudiantes
                WHERE estudiantes.user_id = users.id
            )
            WHERE id IN (SELECT user_id FROM estudiantes)
            """
        )
    )
    op.drop_table("estudiantes")
