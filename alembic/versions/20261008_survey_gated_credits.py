"""Track survey requirements and deferred activity credits.

Revision ID: 20261008_survey_credits
Revises: 20261008_estudiante
Create Date: 2026-10-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261008_survey_credits"
down_revision: Union[str, Sequence[str], None] = "20261008_estudiante"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "actividades" in tables:
        columns = {
            column["name"] for column in sa.inspect(bind).get_columns("actividades")
        }
        if "encuesta_obligatoria" not in columns:
            op.add_column(
                "actividades",
                sa.Column(
                    "encuesta_obligatoria",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.true(),
                ),
            )

    if "asistencia" in tables:
        columns = {
            column["name"] for column in sa.inspect(bind).get_columns("asistencia")
        }
        if "estado_creditos" not in columns:
            op.add_column(
                "asistencia",
                sa.Column(
                    "estado_creditos",
                    sa.String(length=30),
                    nullable=False,
                    server_default="acreditado",
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "asistencia" in tables:
        columns = {
            column["name"] for column in sa.inspect(bind).get_columns("asistencia")
        }
        if "estado_creditos" in columns:
            op.drop_column("asistencia", "estado_creditos")

    if "actividades" in tables:
        columns = {
            column["name"] for column in sa.inspect(bind).get_columns("actividades")
        }
        if "encuesta_obligatoria" in columns:
            op.drop_column("actividades", "encuesta_obligatoria")
