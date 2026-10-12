"""Add searchable tags to FAQs."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261013_faq_tags"
down_revision: Union[str, Sequence[str], None] = "20261012_internal_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "faq",
        sa.Column("tags", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("faq", "tags")
