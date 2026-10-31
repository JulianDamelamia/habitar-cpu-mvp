"""Refactor de usuarios y colaboradores: se crea tabla personas y se asocia a usuarios y docentes."""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261027_usuarios_colaboradores"
down_revision: Union[str, Sequence[str], None] = "20261015_faq_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = inspector.get_table_names()
    if "personas" not in tables:
        op.create_table(
            "personas",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("nombre", sa.String(length=120), nullable=False),
            sa.Column("apellido", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=120), nullable=True, unique=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())
            )

    op.add_column('users', sa.Column('persona_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_persona_id', 'users', 'personas', ['persona_id'], ['id'], ondelete='CASCADE')
    op.add_column('docentes', sa.Column('persona_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_docentes_persona', 'docentes', 'personas', ['persona_id'], ['id'], ondelete='CASCADE')

    op.execute("""
        INSERT INTO personas (nombre, apellido, email, created_at)
        SELECT 
            COALESCE(NULLIF(nombre, ''), 'Sin Nombre') as nombre,
            COALESCE(NULLIF(apellido, ''), 'Sin Apellido') as apellido,
            email,
            created_at
        FROM users
        WHERE email IS NOT NULL AND nombre != '' AND apellido != ''
        ORDER BY email, created_at DESC;
    """)
    op.execute("""
        UPDATE users 
        SET persona_id = personas.id 
        FROM personas 
        WHERE users.email = personas.email;
    """)
    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'email')
    op.drop_column('users', 'nombre')
    op.drop_column('users', 'apellido')
    op.drop_column('users', 'created_at')

    op.drop_constraint('users_docente_id_fkey', 'users', type_='foreignkey')
    op.drop_column('users', 'docente_id')

def downgrade() -> None:
    # Lógica para revertir (volver a agregar las columnas a users y rellenarlas desde personas)
    op.add_column('users', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')))
    op.add_column('users', sa.Column('apellido', sa.String(120), server_default='', nullable=False))
    op.add_column('users', sa.Column('nombre', sa.String(120), server_default='', nullable=False))
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Restaurar datos desde personas
    op.execute("""
        UPDATE users 
        SET email = p.email, nombre = p.nombre, apellido = p.apellido, created_at = p.created_at
        FROM personas p
        WHERE users.persona_id = p.id;
    """)

    # Eliminar restricciones y tablas creadas
    op.drop_constraint('fk_users_persona_id', 'users', type_='foreignkey')
    op.drop_column('users', 'persona_id')
    op.drop_index(op.f('ix_personas_id'), table_name='personas')
    op.drop_table('personas')