"""Add mandatory password change flag to users.

Revision ID: 20261007_debe_cambiar_pw
Revises: 00f97093be0b
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_debe_cambiar_pw"
down_revision: Union[str, Sequence[str], None] = "00f97093be0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")
    }
    if "debe_cambiar_pw" not in columns:
        op.add_column(
            "users",
            sa.Column(
                "debe_cambiar_pw",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    op.drop_column("users", "debe_cambiar_pw")
