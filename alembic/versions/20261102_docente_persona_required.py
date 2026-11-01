"""Move docente identity fields to personas."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261102_docentes_persona"
down_revision: Union[str, Sequence[str], None] = "20261101_user_persona_required"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "docentes" not in inspector.get_table_names():
        return

    persona_columns = {
        column["name"]: column
        for column in inspector.get_columns("personas")
    }
    email_column = persona_columns.get("email")
    if email_column is None:
        raise RuntimeError("Cannot migrate docente identity without personas.email.")
    if not email_column["nullable"]:
        with op.batch_alter_table("personas") as batch_op:
            batch_op.alter_column(
                "email",
                existing_type=email_column["type"],
                nullable=True,
            )

    docente_columns = {
        column["name"]: column
        for column in inspector.get_columns("docentes")
    }
    required_columns = {"id", "persona_id", "nombre", "apellido"}
    if not required_columns <= docente_columns.keys():
        raise RuntimeError(
            "Cannot migrate docentes: expected id, persona_id, nombre, and apellido."
        )

    docentes = sa.Table("docentes", sa.MetaData(), autoload_with=bind)
    personas = sa.Table("personas", sa.MetaData(), autoload_with=bind)
    unlinked_docentes = bind.execute(
        sa.select(
            docentes.c.id,
            docentes.c.nombre,
            docentes.c.apellido,
        ).where(docentes.c.persona_id.is_(None))
    ).mappings().all()
    for docente in unlinked_docentes:
        persona_id = bind.execute(
            sa.insert(personas)
            .values(
                nombre=(docente["nombre"] or "").strip() or "Sin Nombre",
                apellido=(docente["apellido"] or "").strip() or "Sin Apellido",
                email=None,
            )
            .returning(personas.c.id)
        ).scalar_one()
        bind.execute(
            sa.update(docentes)
            .where(docentes.c.id == docente["id"])
            .values(persona_id=persona_id)
        )

    unlinked_count = bind.scalar(
        sa.select(sa.func.count())
        .select_from(docentes)
        .where(docentes.c.persona_id.is_(None))
    )
    if unlinked_count:
        raise RuntimeError("Cannot require docentes.persona_id while links are missing.")

    with op.batch_alter_table("docentes") as batch_op:
        batch_op.alter_column(
            "persona_id",
            existing_type=docente_columns["persona_id"]["type"],
            nullable=False,
        )
        batch_op.drop_column("nombre")
        batch_op.drop_column("apellido")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "docentes" not in inspector.get_table_names():
        return

    docente_columns = {
        column["name"]: column
        for column in inspector.get_columns("docentes")
    }
    persona_id_type = docente_columns["persona_id"]["type"]
    with op.batch_alter_table("docentes") as batch_op:
        batch_op.add_column(sa.Column("nombre", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("apellido", sa.String(length=120), nullable=True))

    op.execute(
        sa.text(
            "UPDATE docentes SET "
            "nombre = (SELECT nombre FROM personas WHERE personas.id = docentes.persona_id), "
            "apellido = (SELECT apellido FROM personas WHERE personas.id = docentes.persona_id)"
        )
    )
    with op.batch_alter_table("docentes") as batch_op:
        batch_op.alter_column(
            "persona_id",
            existing_type=persona_id_type,
            nullable=True,
        )
