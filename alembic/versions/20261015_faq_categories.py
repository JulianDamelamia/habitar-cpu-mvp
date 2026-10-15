"""Add FAQ categories and remove manual FAQ ordering."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261015_faq_categories"
down_revision: Union[str, Sequence[str], None] = "20261014_message_replies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    if "faq_categorias" not in tables:
        op.create_table(
            "faq_categorias",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nombre", sa.String(length=100), nullable=False, unique=True),
        )

    category_table = sa.Table(
        "faq_categorias",
        sa.MetaData(),
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=100), nullable=False),
    )
    category_id = connection.execute(
        sa.select(category_table.c.id).where(category_table.c.nombre == "General")
    ).scalar_one_or_none()
    if category_id is None:
        category_id = connection.execute(
            sa.insert(category_table).values(nombre="General").returning(category_table.c.id)
        ).scalar_one()

    faq_columns = {column["name"] for column in inspector.get_columns("faq")}
    faq_indexes = {index["name"] for index in inspector.get_indexes("faq")}
    faq_foreign_keys = {foreign_key["name"] for foreign_key in inspector.get_foreign_keys("faq")}
    with op.batch_alter_table("faq") as batch_op:
        if "categoria_id" not in faq_columns:
            batch_op.add_column(sa.Column("categoria_id", sa.Integer(), nullable=True))
        if "fk_faq_categoria_id_faq_categorias" not in faq_foreign_keys:
            batch_op.create_foreign_key(
                "fk_faq_categoria_id_faq_categorias",
                "faq_categorias",
                ["categoria_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "ix_faq_categoria_id" not in faq_indexes:
            batch_op.create_index("ix_faq_categoria_id", ["categoria_id"])
        if "orden" in faq_columns:
            batch_op.drop_column("orden")

    connection.execute(
        sa.text("UPDATE faq SET categoria_id = :category_id WHERE categoria_id IS NULL"),
        {"category_id": category_id},
    )


def downgrade() -> None:
    with op.batch_alter_table("faq") as batch_op:
        batch_op.add_column(sa.Column("orden", sa.Integer(), nullable=False, server_default="0"))
        batch_op.drop_constraint("fk_faq_categoria_id_faq_categorias", type_="foreignkey")
        batch_op.drop_index("ix_faq_categoria_id")
        batch_op.drop_column("categoria_id")
    op.drop_table("faq_categorias")
