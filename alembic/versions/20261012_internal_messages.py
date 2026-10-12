"""Add internal direct and broadcast messages."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261012_internal_messages"
down_revision: Union[str, Sequence[str], None] = "20261009_docentes_creditos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mensajes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "remitente_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "destinatario_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("asunto", sa.String(length=200), nullable=False),
        sa.Column("cuerpo", sa.Text(), nullable=False),
        sa.Column("leido", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mensajes_remitente_id", "mensajes", ["remitente_id"])
    op.create_index("ix_mensajes_destinatario_id", "mensajes", ["destinatario_id"])
    op.create_index("ix_mensajes_created_at", "mensajes", ["created_at"])
    op.create_table(
        "mensaje_lecturas",
        sa.Column(
            "mensaje_id",
            sa.Integer(),
            sa.ForeignKey("mensajes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("leido", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("leido_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("mensaje_lecturas")
    op.drop_index("ix_mensajes_created_at", table_name="mensajes")
    op.drop_index("ix_mensajes_destinatario_id", table_name="mensajes")
    op.drop_index("ix_mensajes_remitente_id", table_name="mensajes")
    op.drop_table("mensajes")
