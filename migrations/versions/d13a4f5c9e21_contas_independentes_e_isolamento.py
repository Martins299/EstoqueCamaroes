"""contas independentes e isolamento por estabelecimento

Revision ID: d13a4f5c9e21
Revises: c8922bc4e76a
Create Date: 2026-11-17
"""
from alembic import op
import sqlalchemy as sa


revision = "d13a4f5c9e21"
down_revision = "c8922bc4e76a"
branch_labels = None
depends_on = None


def _add_tenant_column(table):
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("establishment_id", sa.Integer(), nullable=True))


def _finalize_tenant_column(table, ondelete="CASCADE"):
    with op.batch_alter_table(table) as batch:
        batch.alter_column("establishment_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            f"fk_{table}_estabelecimento", "estabelecimentos", ["establishment_id"], ["id"], ondelete=ondelete
        )
        batch.create_index(f"ix_{table}_establishment_id", ["establishment_id"], unique=False)


def upgrade():
    op.create_table(
        "estabelecimentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    bind = op.get_bind()
    bind.execute(sa.text("INSERT INTO estabelecimentos (name, created_at) VALUES (:name, CURRENT_TIMESTAMP)"),
                 {"name": "Estabelecimento existente"})
    legacy_id = bind.execute(sa.text("SELECT id FROM estabelecimentos ORDER BY id LIMIT 1")).scalar_one()

    scoped_tables = ("usuarios", "camaras", "classificacoes", "apresentacoes", "lotes", "movimentacoes")
    for table in scoped_tables:
        _add_tenant_column(table)
        bind.execute(sa.text(f"UPDATE {table} SET establishment_id = :tenant"), {"tenant": legacy_id})

    for table in scoped_tables:
        _finalize_tenant_column(table, "RESTRICT" if table == "usuarios" else "CASCADE")

    convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table("camaras", naming_convention=convention) as batch:
        batch.drop_constraint("camaras_name_key" if bind.dialect.name == "postgresql" else "uq_camaras_name", type_="unique")
        batch.create_unique_constraint("uq_camaras_estabelecimento_nome", ["establishment_id", "name"])
    with op.batch_alter_table("classificacoes", naming_convention=convention) as batch:
        batch.drop_constraint("classificacoes_name_key" if bind.dialect.name == "postgresql" else "uq_classificacoes_name", type_="unique")
        batch.create_unique_constraint("uq_classificacoes_estabelecimento_nome", ["establishment_id", "name"])
    with op.batch_alter_table("apresentacoes", naming_convention=convention) as batch:
        batch.drop_constraint("apresentacoes_name_key" if bind.dialect.name == "postgresql" else "uq_apresentacoes_name", type_="unique")
        batch.create_unique_constraint("uq_apresentacoes_estabelecimento_nome", ["establishment_id", "name"])
    with op.batch_alter_table("lotes") as batch:
        batch.drop_index("ix_lotes_code")
        batch.create_index("ix_lotes_code", ["code"], unique=False)
        batch.create_unique_constraint("uq_lotes_estabelecimento_codigo", ["establishment_id", "code"])


def downgrade():
    raise RuntimeError("A reversão apagaria a separação entre estabelecimentos. Restaure o backup anterior à migração.")
