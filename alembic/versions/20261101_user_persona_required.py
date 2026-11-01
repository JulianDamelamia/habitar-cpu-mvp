"""Require every user to reference a unique persona."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261101_user_persona_required"
down_revision: Union[str, Sequence[str], None] = "20261027_usuarios_colaboradores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _delete_users_without_email(
    bind: sa.Connection, inspector: sa.Inspector
) -> None:
    users = sa.Table("users", sa.MetaData(), autoload_with=bind)
    personas = sa.Table("personas", sa.MetaData(), autoload_with=bind)
    user_ids = (
        sa.select(users.c.id)
        .select_from(users.outerjoin(personas, users.c.persona_id == personas.c.id))
        .where(
            sa.or_(
                users.c.persona_id.is_(None),
                personas.c.email.is_(None),
                sa.func.trim(personas.c.email) == "",
            )
        )
    )
    user_count = bind.scalar(
        sa.select(sa.func.count()).select_from(user_ids.subquery())
    )
    if not user_count:
        return

    for table_name in inspector.get_table_names():
        if table_name in {"users", "personas"}:
            continue
        table = sa.Table(table_name, sa.MetaData(), autoload_with=bind)
        user_fk_columns = [
            table.c[fk["constrained_columns"][0]]
            for fk in inspector.get_foreign_keys(table_name)
            if fk["referred_table"] == "users"
            and len(fk["constrained_columns"]) == 1
        ]
        nullable_columns = [
            column for column in user_fk_columns if column.nullable
        ]
        required_columns = [
            column for column in user_fk_columns if not column.nullable
        ]
        for column in nullable_columns:
            bind.execute(
                sa.update(table)
                .where(column.in_(user_ids))
                .values({column.name: None})
            )
        for column in required_columns:
            bind.execute(sa.delete(table).where(column.in_(user_ids)))

    bind.execute(sa.delete(users).where(users.c.id.in_(user_ids)))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    _delete_users_without_email(bind, inspector)

    duplicate_links = bind.scalar(
        sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT persona_id FROM users GROUP BY persona_id HAVING COUNT(*) > 1"
            ") AS duplicate_personas"
        )
    )
    if duplicate_links:
        raise RuntimeError(
            "Cannot require unique users.persona_id: multiple users share a persona. "
            "Repair those identity records, then retry the migration."
        )

    if "docentes" in tables:
        docente_columns = {
            column["name"] for column in inspector.get_columns("docentes")
        }
        if not {"id", "persona_id", "nombre", "apellido"} <= docente_columns:
            raise RuntimeError(
                "Cannot migrate docentes without their legacy name and surname columns."
            )

        docentes = sa.table(
            "docentes",
            sa.column("id", sa.Integer()),
            sa.column("persona_id", sa.Integer()),
            sa.column("nombre", sa.String()),
            sa.column("apellido", sa.String()),
        )
        personas = sa.table(
            "personas",
            sa.column("id", sa.Integer()),
            sa.column("nombre", sa.String()),
            sa.column("apellido", sa.String()),
            sa.column("email", sa.String()),
        )
        users = sa.table(
            "users",
            sa.column("id", sa.Integer()),
            sa.column("persona_id", sa.Integer()),
            sa.column("rol", sa.String()),
        )
        linked_personas = set(
            bind.execute(
                sa.select(docentes.c.persona_id).where(
                    docentes.c.persona_id.is_not(None)
                )
            ).scalars()
        )
        missing_docentes = bind.execute(
            sa.select(
                docentes.c.id,
                docentes.c.nombre,
                docentes.c.apellido,
            ).where(docentes.c.persona_id.is_(None))
        ).mappings()
        for docente in missing_docentes:
            nombre = (docente["nombre"] or "").strip() or "Sin Nombre"
            apellido = (docente["apellido"] or "").strip() or "Sin Apellido"
            candidates = bind.execute(
                sa.select(personas.c.id)
                .select_from(personas.join(users, users.c.persona_id == personas.c.id))
                .where(
                    users.c.rol != "estudiante",
                    sa.func.lower(sa.func.trim(personas.c.nombre))
                    == nombre.lower(),
                    sa.func.lower(sa.func.trim(personas.c.apellido))
                    == apellido.lower(),
                )
            ).scalars().all()
            candidate_id = (
                candidates[0]
                if len(candidates) == 1 and candidates[0] not in linked_personas
                else None
            )
            if candidate_id is None:
                continue
            bind.execute(
                sa.update(docentes)
                .where(docentes.c.id == docente["id"])
                .values(persona_id=candidate_id)
            )
            linked_personas.add(candidate_id)

        duplicate_docentes = bind.execute(
            sa.select(
                docentes.c.persona_id,
                sa.func.min(docentes.c.id).label("keep_id"),
            )
            .where(docentes.c.persona_id.is_not(None))
            .group_by(docentes.c.persona_id)
            .having(sa.func.count() > 1)
        ).all()
        for persona_id, keep_id in duplicate_docentes:
            bind.execute(
                sa.update(docentes)
                .where(
                    docentes.c.persona_id == persona_id,
                    docentes.c.id != keep_id,
                )
                .values(persona_id=None)
            )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "persona_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_unique_constraint("uq_users_persona_id", ["persona_id"])
    if "docentes" in tables:
        with op.batch_alter_table("docentes") as batch_op:
            batch_op.create_unique_constraint(
                "uq_docentes_persona_id", ["persona_id"]
            )


def downgrade() -> None:
    if "docentes" in sa.inspect(op.get_bind()).get_table_names():
        with op.batch_alter_table("docentes") as batch_op:
            batch_op.drop_constraint("uq_docentes_persona_id", type_="unique")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("uq_users_persona_id", type_="unique")
        batch_op.alter_column(
            "persona_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
