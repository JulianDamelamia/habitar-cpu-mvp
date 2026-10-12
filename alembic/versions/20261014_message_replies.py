"""Link internal message replies to original messages."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261014_message_replies"
down_revision: Union[str, Sequence[str], None] = "20261013_faq_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mensajes",
        sa.Column(
            "reply_to_id",
            sa.Integer(),
            sa.ForeignKey("mensajes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_mensajes_reply_to_id", "mensajes", ["reply_to_id"])


def downgrade() -> None:
    op.drop_index("ix_mensajes_reply_to_id", table_name="mensajes")
    op.drop_column("mensajes", "reply_to_id")
